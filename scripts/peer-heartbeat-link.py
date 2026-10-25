"""Operator-installed TLS peer transport with optional bounded native analysis.

The local Kingdom remains authoritative for identity, revocation and replay checks.
Server has no owner token. Client uses its own token only on local loopback.
"""
import argparse
import json
import ssl
import time
import subprocess
import urllib.request
import http.cookiejar
from urllib.parse import urlsplit
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

LIMIT = 262144
ANALYSIS_TOOLS={'text.analyze@1.0.0','code.python.analyze@1.0.0'}


def validate_mesh_rpc(message, config):
    kind=message.get('msg_type')
    if message.get('target_id')!=config['identity']['node_id']:
        raise ValueError('Wrong target')
    if kind in {'heartbeat','inventory_snapshot','mesh_roster_request','mesh_roster_response'}:
        return
    if config.get('analysis_enabled') is not True or kind not in {'task_poll','task_result'}:
        raise ValueError('Execution RPC is not exposed by the peer listener')
    payload=message.get('payload')
    if not isinstance(payload,dict):raise ValueError('Expected a typed analysis payload')
    if kind=='task_poll':
        tools=payload.get('supported_tools')
        if (not isinstance(tools,list) or not tools or len(tools)>2
                or any(not isinstance(t,str) or t not in ANALYSIS_TOOLS for t in tools)
                or len(set(tools))!=len(tools) or payload.get('require_running') is not True):
            raise ValueError('Only stopped-state-aware native analysis polls are supported')
    else:
        if payload.get('status') not in {'completed','failed'}:
            raise ValueError('Expected an analysis result')
        if payload['status']=='completed':
            output=payload.get('output')
            if not isinstance(output,dict) or output.get('kind')!='native_tool' or output.get('tool') not in ANALYSIS_TOOLS:
                raise ValueError('Only pure analysis results are supported')
    # Native RPC still verifies signature, current compute grant, exact lease,
    # fencing and independently recomputes the actual assigned tool result.


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def request(url, payload=None, token=None, context=None, opener=None):
    headers = {'Content-Type': 'application/json', 'X-Kingdom-Request': '1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    # Fixed URLs only: never follow redirects with an owner credential.
    opener = opener or urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}),
                                                   urllib.request.HTTPSHandler(context=context))
    with opener.open(req, timeout=6) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Oversized peer report')
    return json.loads(raw)


def validate_envelope(message, sender, target, kind):
    if (not isinstance(message, dict) or message.get('sender_id') != sender
            or message.get('target_id') != target or message.get('msg_type') != kind
            or message.get('protocol_version') != 'kingdom.cluster.v1'):
        raise ValueError('Unexpected heartbeat envelope')
    return message


def identity(local, expected):
    found = request(local + '/nodes/identity')
    if any(found.get(k) != expected[k] for k in ('node_id', 'fingerprint')):
        raise ValueError('Pinned Kingdom identity changed')


def make_handler(config):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(7)

        def log_message(self, *args):
            pass  # Do not log remote report contents or credentials.

        def do_GET(self):
            if not config.get('mesh_enabled') or self.path != '/nodes/identity':
                self.send_error(404)
                return
            try:
                identity(config['local'], config['identity'])
                body = json.dumps(request(config['local'] + '/nodes/identity')).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
            except Exception:
                self.send_error(503, 'Peer unavailable')

        def do_POST(self):
            try:
                mesh_path = config.get('mesh_enabled') and self.path in {'/nodes/rpc', '/nodes/pair'}
                if (self.path != '/heartbeat' and not mesh_path) or self.headers.get('Transfer-Encoding'):
                    self.send_error(404)
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= LIMIT:
                    raise ValueError('Invalid body size')
                message = json.loads(self.rfile.read(size))
                if mesh_path:
                    if not isinstance(message, dict):
                        raise ValueError('Expected an object')
                    if self.path == '/nodes/rpc':
                        validate_mesh_rpc(message,config)
                    identity(config['local'], config['identity'])
                    result = request(config['local'] + self.path, message)
                    body = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                    return
                sender = message.get('sender_id') if isinstance(message, dict) else None
                if sender not in config['peers']:
                    raise ValueError('Unconfigured peer')
                validate_envelope(message, sender, config['identity']['node_id'], 'heartbeat')
                identity(config['local'], config['identity'])
                # Native RPC verifies signature, current approval and durable replay ledger.
                result = request(config['local'] + '/nodes/rpc', message)
                if not result.get('ping', {}).get('success'):
                    raise ValueError('Report was not accepted')
                proof = validate_envelope(result.get('inventory_proof'), config['identity']['node_id'], sender, 'inventory_snapshot')
                body = json.dumps(proof).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(403, 'Heartbeat rejected')
    return Handler


def local_client(config):
    local = urlsplit(config['local'])
    if local.scheme != 'http' or local.hostname not in {'127.0.0.1', 'localhost', '::1'} or local.username or local.password or local.path or local.query or local.fragment:
        raise ValueError('Local owner access requires an exact loopback origin')
    if config.get('auth_mode') == 'local_session':
        # Use the documented same-computer session flow, never extract a native
        # process credential. Cookies stay in memory and only on loopback.
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        invoke = lambda path, body=None: request(config['local'] + path, body, opener=opener)
        if invoke('/auth/local/status', {}).get('passcode_enabled') is not False:
            raise ValueError('Owner unlock required; startup passcode is preserved')
        if invoke('/auth/local/session', {}).get('identity') != 'owner':
            raise ValueError('Local session was not authorized')
        return invoke
    token = Path(config['token_file']).read_text().strip()
    return lambda path, body=None: request(config['local'] + path, body, token)


def sync(config):
    identity(config['local'], config['identity'])
    invoke = local_client(config)
    proof = invoke('/federation/' + config['peer_id'] + '/heartbeat-proof', {})
    validate_envelope(proof, config['identity']['node_id'], config['peer_id'], 'heartbeat')
    if config.get('transport') == 'pinned_ssh':
        # Existing operator-approved SSH identity, not port forwarding. The
        # fixed remote program can only submit this signed report to loopback.
        program = f'''import json,urllib.request
message={proof!r}
with urllib.request.urlopen('http://127.0.0.1:{int(config['peer_port'])}/nodes/identity',timeout=6) as r:identity=json.load(r)
assert identity['node_id']=={config['peer_id']!r} and identity['fingerprint']=={config['peer_fingerprint']!r}
req=urllib.request.Request('http://127.0.0.1:{int(config['peer_port'])}/nodes/rpc',data=json.dumps(message).encode(),headers={{'Content-Type':'application/json'}})
with urllib.request.urlopen(req,timeout=6) as r:
 data=r.read({LIMIT + 1})
 assert len(data)<={LIMIT}
 print(data.decode())
'''
        completed = subprocess.run(config['ssh_command'] + [config['remote_python'] + ' -'],
                                   input=program, text=True, capture_output=True, timeout=18)
        if completed.returncode or len(completed.stdout) > LIMIT:
            raise ValueError('Pinned peer transport failed')
        result = json.loads(completed.stdout)
        if not result.get('ping', {}).get('success'):
            raise ValueError('Peer heartbeat was not accepted')
        reply = result.get('inventory_proof')
    else:
        context = ssl.create_default_context(cafile=config['ca_file'])
        origins = [config['remote'], *config.get('remote_fallbacks', [])]
        if len(origins) > 3 or any(not origin.startswith('https://') for origin in origins):
            raise ValueError('Use up to three owner-configured HTTPS routes')
        for index, origin in enumerate(origins):
            try:
                reply = request(origin + '/heartbeat', proof, context=context)
                break
            except urllib.error.HTTPError:
                raise  # An authorization rejection is never a reason to switch routes.
            except (urllib.error.URLError, TimeoutError):
                if index + 1 == len(origins):
                    raise
    validate_envelope(reply, config['peer_id'], config['identity']['node_id'], 'inventory_snapshot')
    accepted = invoke('/nodes/rpc', reply)
    if not accepted.get('ping', {}).get('success'):
        raise ValueError('Peer response was not accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if config['mode'] == 'server':
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(config['cert_file'], config['key_file'])
        class TLSServer(HTTPServer):
            request_queue_size = 8

            def get_request(self):
                sock, address = self.socket.accept()
                sock.settimeout(6)
                try:
                    return tls.wrap_socket(sock, server_side=True), address
                except Exception:
                    sock.close()
                    raise
        server = TLSServer((config['bind'], config['port']), make_handler(config))
        server.serve_forever()
    else:
        if config.get('transport') != 'pinned_ssh' and not config['remote'].startswith('https://'):
            raise ValueError('Peer transport requires TLS')
        failures = 0
        while True:
            started = time.monotonic()
            state = {'observed_at': time.time(), 'peer_id': config['peer_id']}
            try:
                sync(config)
                failures = 0
                state['status'] = 'verified'
            except Exception as error:
                failures += 1
                state.update(status='unavailable', error_class=type(error).__name__)
            path = Path(config['state_file'])
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(path)
            time.sleep(max(1, min(30, 15 + failures * 2) - (time.monotonic() - started)))


if __name__ == '__main__':
    main()

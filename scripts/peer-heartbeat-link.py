"""Operator-installed TLS heartbeat transport; never forwards execution RPCs.

The local Kingdom remains authoritative for identity, revocation and replay checks.
Server has no owner token. Client uses its own token only on local loopback.
"""
import argparse
import json
import ssl
import time
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

LIMIT = 262144


def request(url, payload=None, token=None, context=None):
    headers = {'Content-Type': 'application/json', 'X-Kingdom-Request': '1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    # Fixed URLs only: never follow redirects with an owner credential.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}),
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

        def do_POST(self):
            try:
                if self.path != '/heartbeat' or self.headers.get('Transfer-Encoding'):
                    self.send_error(404)
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= LIMIT:
                    raise ValueError('Invalid body size')
                message = json.loads(self.rfile.read(size))
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


def sync(config):
    identity(config['local'], config['identity'])
    token = Path(config['token_file']).read_text().strip()
    proof = request(config['local'] + '/federation/' + config['peer_id'] + '/heartbeat-proof', {}, token)
    validate_envelope(proof, config['identity']['node_id'], config['peer_id'], 'heartbeat')
    context = ssl.create_default_context(cafile=config['ca_file'])
    reply = request(config['remote'] + '/heartbeat', proof, context=context)
    validate_envelope(reply, config['peer_id'], config['identity']['node_id'], 'inventory_snapshot')
    accepted = request(config['local'] + '/nodes/rpc', reply)
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
        if not config['remote'].startswith('https://'):
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

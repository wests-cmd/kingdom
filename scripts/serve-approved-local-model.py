"""TLS proxy to one local model; optional bounded tool-call text, never execution."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import threading
import urllib.request


FILE_TOOLS={'workspace_read','workspace_write','workspace_list'}


def bounded_payload(raw, model, allowed_tools=()):
    if len(raw) > 65536:
        raise ValueError('Request too large')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('model') != model or data.get('stream') is not False:
        raise ValueError('Only the configured model and non-streaming inference are allowed')
    if set(data) - {'model','messages','prompt','stream','options','think','format','tools'}:
        raise ValueError('Unsupported inference parameter')
    if data.get('tools'):
        tools=data['tools'];allowed=set(allowed_tools)
        if (not allowed or not allowed<=FILE_TOOLS or not isinstance(tools,list)
                or len(tools)>3 or len(json.dumps(tools))>16000):
            raise ValueError('Tool-call generation is not enabled for this request')
        names=set()
        for tool in tools:
            function=tool.get('function') if isinstance(tool,dict) else None
            if (not isinstance(function,dict) or tool.get('type')!='function'
                    or function.get('name') not in allowed or function['name'] in names
                    or not isinstance(function.get('parameters'),dict)):
                raise ValueError('Unsupported tool-call schema')
            names.add(function['name'])
    if not isinstance(data.get('options', {}), dict):
        raise ValueError('Invalid model options')
    options = data.get('options', {})
    for name, default, ceiling in [('num_ctx',4096,4096),('num_predict',512,1024)]:
        value = options.get(name, default)
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError('Inference resource budget exceeded')
    # Do not permit callers to change memory, GPU loading or server threading.
    data['options'] = {'num_ctx':options.get('num_ctx',4096),
                       'num_predict':options.get('num_predict',512)}
    data['think'] = False
    return data


def handler(config, forward):
    semaphore = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_args):
            pass  # Never log credentials, prompts or provider responses.

        def answer(self, code, data):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if self.client_address[0] not in config['allowed_ips']:
                self.answer(403, {'error':'client_not_allowed'});return False
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+config['token']):
                self.answer(401, {'error':'authentication_required'});return False
            return True

        def do_GET(self):
            if not self.authorized():return
            if self.path == '/health':
                self.answer(200, {'status':'ready','node_id':config['node_id'],
                                  'model':config['model'],'scope':'bounded file-tool call generation; no execution' if config.get('allowed_tools') else 'planning text only'})
            elif self.path == '/api/tags':
                try:
                    inventory=forward('/api/tags',None)
                    models=[m for m in inventory.get('models',[]) if (m.get('name') or m.get('model'))==config['model']]
                    self.answer(200, {'models':[{'name':config['model'],'model':config['model']}] if models else []})
                except Exception:self.answer(503, {'error':'local_model_unavailable'})
            else:self.answer(404, {'error':'route_not_allowed'})

        def do_POST(self):
            if not self.authorized():return
            if self.path not in {'/api/chat','/api/generate'}:
                self.answer(404, {'error':'route_not_allowed'});return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 65536:raise ValueError()
                payload = bounded_payload(self.rfile.read(length), config['model'],config.get('allowed_tools',()))
                if self.path == '/api/chat' and not isinstance(payload.get('messages'),list):raise ValueError()
                if self.path == '/api/generate' and not isinstance(payload.get('prompt'),str):raise ValueError()
            except (ValueError, TypeError, UnicodeError):
                self.answer(400, {'error':'invalid_or_out_of_scope_request'});return
            if not semaphore.acquire(blocking=False):
                self.answer(503, {'error':'local_model_busy'});return
            try:
                result = forward(self.path,payload)
                self.answer(200,result)
            except Exception:
                self.answer(503, {'error':'local_model_unavailable'})
            finally:semaphore.release()
    return Handler


class TLSModelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, request_handler, context, allowed_ips):
        self.context, self.allowed_ips = context, set(allowed_ips)
        self.connections = threading.BoundedSemaphore(8)
        super().__init__(address, request_handler)

    def get_request(self):
        connection, address = super().get_request()
        if address[0] not in self.allowed_ips:
            connection.close();raise OSError('Unapproved client')
        connection.settimeout(10)
        try:return self.context.wrap_socket(connection,server_side=True), address
        except Exception:
            connection.close();raise

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request);return
        try:super().process_request(request,address)
        except Exception:
            self.connections.release();raise

    def process_request_thread(self, request, address):
        try:super().process_request_thread(request,address)
        finally:self.connections.release()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    args=parser.parse_args();config=json.loads(Path(args.config).read_text())
    if not config['token'] or len(config['token']) < 32:raise ValueError('Authentication must be configured')
    allowed=config.get('allowed_tools',[])
    if not isinstance(allowed,list) or any(not isinstance(t,str) or t not in FILE_TOOLS for t in allowed) or len(set(allowed))!=len(allowed):
        raise ValueError('Configure only distinct bounded file-tool names')
    # Upstream is fixed at installation; client input never chooses a URL.
    if config['upstream'] != 'http://127.0.0.1:11435':raise ValueError('Unsupported upstream')
    def forward(route,payload):
        request=urllib.request.Request(config['upstream']+route,
            data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=590) as response:
            content=response.read(262145)
        if len(content)>262144:raise ValueError('Response exceeds budget')
        return json.loads(content)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config['certificate'],config['private_key'])
    server=TLSModelServer(('0.0.0.0',config['port']),handler(config,forward),context,config['allowed_ips'])
    server.serve_forever()


if __name__=='__main__':main()

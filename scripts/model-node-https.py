"""Authenticated model-only HTTPS endpoint; Ollama stays on loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import http.client
import json
import os
from pathlib import Path
import ssl

ROOT = Path.home()/'.local/share/kingdom-model-node'
TOKEN = (ROOT/'api-token').read_text().strip()
ALLOWED = {'/api/tags', '/api/generate', '/v1/models', '/v1/chat/completions'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def handle_model(self):
        if not hmac.compare_digest(self.headers.get('Authorization','').encode(), ('Bearer '+TOKEN).encode()):
            self.send_error(401); return
        if self.path not in ALLOWED or self.command not in {'GET','POST'}:
            self.send_error(404); return
        body = None
        if self.command == 'POST':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 2*1024*1024: self.send_error(413); return
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict): self.send_error(400); return
                if payload.get('stream'): self.send_error(400, 'Use buffered inference'); return
                payload['stream']=False
                if self.path == '/api/generate':
                    options=payload.setdefault('options',{})
                    options.update(num_thread=1, num_ctx=max(512,min(int(options.get('num_ctx',65536)),65536)),
                                   num_predict=max(1,min(int(options.get('num_predict',512)),2048)))
                    payload['think']=False
                else:
                    payload['max_tokens']=max(1,min(int(payload.get('max_tokens',512)),2048))
                    payload['reasoning_effort']='none'
                body=json.dumps(payload).encode()
            except (ValueError, TypeError): self.send_error(400); return
        conn=http.client.HTTPConnection('127.0.0.1',11434,timeout=600)
        try:
            conn.request(self.command,self.path,body,{'Content-Type':'application/json'})
            response=conn.getresponse(); data=response.read(8*1024*1024+1)
            if len(data)>8*1024*1024: self.send_error(502); return
            self.send_response(response.status)
            self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)
        except (OSError, http.client.HTTPException): self.send_error(502)
        finally: conn.close()
    do_GET=handle_model
    do_POST=handle_model

server=ThreadingHTTPServer((os.environ.get('KINGDOM_MODEL_BIND','127.0.0.1'),11436),Handler)
server.timeout=30
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version=ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(str(ROOT/'server-cert.pem'),str(ROOT/'server-key.pem'))
server.socket=ctx.wrap_socket(server.socket,server_side=True)
server.serve_forever()

import json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from contextlib import contextmanager
import pytest
from backend.cluster.federation_api import endpoint,check_identity,connect_peer
from backend.cluster.identity import KingdomIdentity

@contextmanager
def peer_server(peer):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(peer.get_public_identity()).encode())
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(body)
            identity=body['knight_public_identity']
            proof=f"{body['code']}:{identity['node_id']}:{peer.node_id}".encode()
            valid=KingdomIdentity.verify_signature(identity['public_key_hex'],proof,bytes.fromhex(body['signature']))
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'success':valid}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',received
    finally:server.shutdown();server.server_close();thread.join()

@pytest.mark.asyncio
async def test_different_kingdom_pairing_uses_own_identity_and_signature():
    own=KingdomIdentity('KG-local');peer=KingdomIdentity('KG-remote')
    inv={'code':'1234-5678','kingdom_id':peer.node_id,'kingdom_fingerprint':peer.fingerprint,'kingdom_public_key_hex':peer.public_bytes.hex()}
    with peer_server(peer) as (url,received):
        result=await connect_peer(url,inv,['compute'],own)
    assert result['status']=='pending_remote_approval'
    assert received[0]['knight_public_identity']['node_id']=='KG-local'
    assert received[0]['requested_capabilities']==['compute']

@pytest.mark.asyncio
async def test_changed_peer_identity_never_sends_pairing_request():
    own=KingdomIdentity('KG-local');peer=KingdomIdentity('KG-remote')
    with peer_server(peer) as (url,received):
        with pytest.raises(ValueError,match='pinned'):
            await connect_peer(url,{'kingdom_id':'different'},['compute'],own)
    assert not received

@pytest.mark.parametrize('url',['http://remote.example','https://user:password@example.com','https://example.com/path','file:///tmp/a'])
def test_insecure_or_credential_urls_rejected(url):
    with pytest.raises(ValueError):endpoint(url)

def test_unique_new_identity_and_preserved_existing(tmp_path):
    a=KingdomIdentity.get_or_create(str(tmp_path/'a.json'))
    b=KingdomIdentity.get_or_create(str(tmp_path/'b.json'))
    assert a.node_id!=b.node_id
    assert KingdomIdentity.get_or_create(str(tmp_path/'a.json')).fingerprint==a.fingerprint
    with pytest.raises(ValueError,match='different Kingdom'):
        check_identity(a.get_public_identity(),a.get_public_identity(),a)

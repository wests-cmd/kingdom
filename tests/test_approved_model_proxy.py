import importlib.util
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
import urllib.error
import urllib.request

import pytest

spec=importlib.util.spec_from_file_location('approved_proxy',Path(__file__).parents[1]/'scripts/serve-approved-local-model.py')
proxy=importlib.util.module_from_spec(spec);spec.loader.exec_module(proxy)


@pytest.mark.parametrize('change',[
    {'model':'other'},{'stream':True},{'tools':[{'name':'shell'}]},
    {'options':{'num_predict':-1}},{'options':{'num_ctx':100000}},
    {'options':{'num_ctx':True}},{'callback':'https://outside.example'}])
def test_out_of_scope_inference_is_rejected(change):
    with pytest.raises(ValueError):proxy.bounded_payload(json.dumps({'model':'small','stream':False,**change}).encode(),'small')


def test_proxy_rejects_oversize_and_strips_resource_overrides():
    with pytest.raises(ValueError):proxy.bounded_payload(b' '*65537,'small')
    result=proxy.bounded_payload(json.dumps({'model':'small','stream':False,'think':True,
        'options':{'num_ctx':2048,'num_predict':128,'num_gpu':99,'num_thread':100}}).encode(),'small')
    assert result['think'] is False and result['options']=={'num_ctx':2048,'num_predict':128}


def test_file_tool_generation_requires_explicit_opt_in_and_never_exposes_processes():
    tool={'type':'function','function':{'name':'workspace_read','parameters':{'type':'object'}}}
    data={'model':'small','stream':False,'messages':[],'tools':[tool]}
    raw=json.dumps(data).encode()
    with pytest.raises(ValueError):proxy.bounded_payload(raw,'small')
    assert proxy.bounded_payload(raw,'small',['workspace_read'])['tools']==[tool]
    for tools in ([tool,tool],[{**tool,'function':{'name':'process_run','parameters':{}}}], [{'type':'function','function':{'name':'workspace_read','parameters':[]}}]):
        with pytest.raises(ValueError):proxy.bounded_payload(json.dumps({**data,'tools':tools}).encode(),'small',['workspace_read'])


def test_actual_http_auth_routes_and_allowed_source_before_upstream():
    calls=[]
    config={'allowed_ips':['127.0.0.1'],'token':'test-secret','model':'small','node_id':'known'}
    def forward(route,payload):calls.append((route,payload));return {'response':'proposal'}
    server=ThreadingHTTPServer(('127.0.0.1',0),proxy.handler(config,forward))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    def call(route,body=None,auth=True):
        request=urllib.request.Request(url+route,data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization':'Bearer test-secret'} if auth else {})
        return json.load(urllib.request.urlopen(request,timeout=2))
    try:
        with pytest.raises(urllib.error.HTTPError) as error:call('/health',auth=False)
        assert error.value.code==401 and calls==[]
        assert call('/health')['node_id']=='known'
        with pytest.raises(urllib.error.HTTPError) as error:call('/api/delete',{'model':'small','stream':False})
        assert error.value.code==404 and calls==[]
        assert call('/api/generate',{'model':'small','stream':False,'prompt':'test'})=={'response':'proposal'}
        assert len(calls)==1
        config['allowed_ips']=[]
        with pytest.raises(urllib.error.HTTPError) as error:call('/health')
        assert error.value.code==403
    finally:server.shutdown();server.server_close();thread.join(2)


def test_real_tls_requires_pinned_certificate_and_authentication(tmp_path):
    import datetime,ipaddress,ssl
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'test-known-knight')])
    now=datetime.datetime.now(datetime.timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1))
        .not_valid_after(now+datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .sign(key,hashes.SHA256()))
    pem=cert.public_bytes(serialization.Encoding.PEM)
    (tmp_path/'cert.pem').write_bytes(pem)
    (tmp_path/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(tmp_path/'cert.pem',tmp_path/'key.pem')
    config={'allowed_ips':['127.0.0.1'],'token':'test-secret','model':'small','node_id':'known'}
    server=proxy.TLSModelServer(('127.0.0.1',0),proxy.handler(config,lambda *_: {}),ctx,config['allowed_ips'])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='https://127.0.0.1:'+str(server.server_port)+'/health'
    try:
        with pytest.raises(urllib.error.URLError):urllib.request.urlopen(url,timeout=2)
        trusted=ssl.create_default_context(cadata=pem.decode())
        with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(url,context=trusted,timeout=2)
        assert error.value.code==401
        request=urllib.request.Request(url,headers={'Authorization':'Bearer test-secret'})
        assert json.load(urllib.request.urlopen(request,context=trusted,timeout=2))['node_id']=='known'
    finally:server.shutdown();server.server_close();thread.join(2)

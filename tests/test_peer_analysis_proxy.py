import copy,json,threading,types,unittest,urllib.request,urllib.error
from unittest.mock import patch
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('link',Path(__file__).parents[1]/'scripts/peer-heartbeat-link.py')
link=importlib.util.module_from_spec(spec);spec.loader.exec_module(link)
class AnalysisProxyTests(unittest.TestCase):
 def setUp(self):
  self.config={'identity':{'node_id':'worker','fingerprint':'finger'},'mesh_enabled':True,'analysis_enabled':True,'local':'http://127.0.0.1:8014'}
  self.offer={'target_id':'worker','msg_type':'native_analysis_execute','payload':{'task':{'id':'task','status':'leased','assigned_knight':'worker','lease_id':'lease','fencing_token':1,'metadata':{'execution_target':'remote','capability':'compute','tool':'text.analyze@1.0.0','tool_parameters':{'text':'literal'}}},'lease':{'task_id':'task','assigned_node_id':'worker','lease_id':'lease','fencing_token':1,'capability_scope':'compute','issued_at':1,'expires_at':61,'revoked':False}}}
 def test_valid_offer(self):link.validate_mesh_rpc(self.offer,self.config)
 def test_negative_boundary(self):
  mutations=[lambda m:m.update(target_id='wrong'),lambda m:m['payload'].update(extra=True),lambda m:m['payload']['task']['metadata'].update(tool='process.execute@1.0.0'),lambda m:m['payload']['task']['metadata'].update(tool_parameters={'path':'/etc/passwd'}),lambda m:m['payload']['lease'].update(fencing_token=2),lambda m:m['payload']['lease'].update(assigned_node_id='wrong'),lambda m:m['payload']['lease'].update(revoked=True),lambda m:m['payload']['task']['metadata'].update(tool_parameters={'text':'x'*262145})]
  for mutate in mutations:
   v=copy.deepcopy(self.offer);mutate(v)
   with self.assertRaises(ValueError):link.validate_mesh_rpc(v,self.config)
  with self.assertRaises(ValueError):link.validate_mesh_rpc(self.offer,{**self.config,'analysis_enabled':False})
 def test_actual_http_request_forwards_signed_message_unchanged(self):
  server=link.HTTPServer(('127.0.0.1',0),link.make_handler(self.config));thread=threading.Thread(target=server.serve_forever);thread.start()
  try:
   with patch.object(link,'identity'),patch.object(link,'request',return_value={'signed':'backend-result'}) as request:
    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/nodes/rpc',data=json.dumps(self.offer).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as response:self.assertEqual(response.status,200)
    request.assert_called_once_with(self.config['local']+'/nodes/rpc',self.offer)
   with patch.object(link,'identity'),patch.object(link,'request') as request:
    invalid=copy.deepcopy(self.offer);invalid['payload']['lease']['fencing_token']=2
    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/nodes/rpc',data=json.dumps(invalid).encode())
    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
    self.assertEqual(error.exception.code,403);request.assert_not_called()
  finally:server.shutdown();thread.join();server.server_close()
if __name__=='__main__':unittest.main()

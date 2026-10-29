"""Controller unit tests. Transport/OS seams here are never production verdicts."""
import base64,copy,importlib.util,json,os,time,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
if os.name!='posix':
 import pytest
 pytest.skip('Protected external Docker controller is POSIX-only',allow_module_level=True)
s=importlib.util.spec_from_file_location('oracle',Path(__file__).parents[1]/'scripts/jules-external-oracle.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
s=importlib.util.spec_from_file_location('backlog_oracle',Path(__file__).parents[1]/'scripts/jules-backlog-oracle.py');backlog=importlib.util.module_from_spec(s);s.loader.exec_module(backlog)
class OracleTests(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir();(self.source/'example.py').write_text('value=1\n')
  self.config={'repository':'wests-cmd/kingdom','source':'sources/github/wests-cmd/kingdom','revision':'a'*40,'image':'sha256:'+'b'*64,'container_name':'kingdom-fixture','deadline_at':time.time()+120,'candidate_patch_sha256':'c'*64,'output_dir':str(self.root/'out'),'source_directory':str(self.source),'source_tree_sha256':m.source_tree_hash(self.source),'test_auth_token':'fixture-token-not-a-real-key'}
  self.path=self.root/'config.json';self.path.write_text(json.dumps(self.config));self.path.chmod(0o600)
 def tearDown(self):self.temp.cleanup()
 def transport(self,method,path,headers,body):
  authenticated=headers.get('Authorization')=='Bearer '+self.config['test_auth_token']
  if path=='/health/live':status,data=200,{'status':'live'}
  elif path=='/integrations/jules/settings':
   status,data=(200,{'enabled':False,'allowed_repositories':['wests-cmd/kingdom'],'allowed_sources':[self.config['source']],'revision':1,'has_credentials':False}) if authenticated else (403,{'detail':'denied'})
  elif path=='/diagnostics/full-scan':status,data=(200,{'status':'clean'}) if authenticated else (403,{'detail':'denied'})
  elif path.startswith('/integrations/jules/jobs/'):status,data=404,{'detail':'not found'}
  else:status,data=403,{'detail':'denied'}
  return {'status':status,'body':base64.b64encode(json.dumps(data).encode()).decode(),'truncated':False}
 def oracle(self,transport=None):return m.ExternalOracle(self.path,transport_fn=transport or self.transport)
 def test_complete_authenticated_fixture_passes_seven_fixed_fences(self):
  record,path=self.oracle().run_suite();self.assertEqual(record['verdict'],'PASSED');self.assertEqual(record['trusted_test_counts'],{'total':7,'passed':7,'failed':0});self.assertEqual(Path(path).stat().st_mode&0o777,0o600)
  self.assertNotIn(self.config['test_auth_token'],Path(path).read_text())
 def test_candidate_stdout_xml_and_error_response_cannot_forge_verdict(self):
  def forged(*args):return {'status':500,'body':base64.b64encode(b'7 passed <testsuite tests="7"/>').decode(),'truncated':False}
  record,_=self.oracle(forged).run_suite();self.assertEqual(record['verdict'],'FAILED');self.assertEqual(record['trusted_test_counts']['failed'],7)
 def test_malformed_authenticated_settings_is_unknown_not_disabled(self):
  def malformed(method,path,headers,body):
   result=self.transport(method,path,headers,body)
   if path=='/integrations/jules/settings' and result['status']==200:result['body']=base64.b64encode(b'{bad-json').decode()
   return result
  record,_=self.oracle(malformed).run_suite();case=next(r for r in record['assertion_results'] if r['name']=='default_off_jules_settings');self.assertFalse(case['passed'])
 def test_truncated_probes_fail_even_when_prefix_looks_valid(self):
  def truncated(*args):return {**self.transport(*args),'truncated':True}
  record,_=self.oracle(truncated).run_suite();self.assertEqual(record['trusted_test_counts']['failed'],7)
 def test_missing_real_endpoint_fails_instead_of_becoming_auth_or_default_proof(self):
  def missing(method,path,headers,body):
   result=self.transport(method,path,headers,body)
   if path=='/integrations/jules/settings':result['status']=404
   return result
  record,_=self.oracle(missing).run_suite();self.assertEqual(record['verdict'],'FAILED')
 def test_validation_error_is_not_proof_of_unauthenticated_write_rejection(self):
  def validation_only(method,path,headers,body):
   result=self.transport(method,path,headers,body)
   if method=='POST':result['status']=422
   return result
  record,_=self.oracle(validation_only).run_suite()
  case=next(row for row in record['assertion_results'] if row['name']=='unauthenticated_write_rejection')
  self.assertFalse(case['passed'])
 def test_diagnostic_fixture_token_leak_fails_without_recording_the_token(self):
  def leak(method,path,headers,body):
   result=self.transport(method,path,headers,body)
   if path=='/diagnostics/full-scan':result['body']=base64.b64encode(json.dumps({'token':self.config['test_auth_token']}).encode()).decode()
   return result
  record,output=self.oracle(leak).run_suite()
  case=next(row for row in record['assertion_results'] if row['name']=='credential_redaction')
  self.assertFalse(case['passed']);self.assertNotIn(self.config['test_auth_token'],Path(output).read_text())
 def metadata(self):
  return {'Id':'d'*64,'State':{'Running':True},'Image':self.config['image'],'Config':{'User':'1000:1000','Labels':{'kingdom.external-oracle':self.config['revision']},'Entrypoint':['python'],'Cmd':['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8012','--no-access-log'],'WorkingDir':'/data','Env':['PYTHONPATH=/workspace']},'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapAdd':[],'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'Memory':128*1024*1024,'NanoCpus':250000000,'PidsLimit':64},'Mounts':[{'Type':'bind','Source':str(self.source),'Destination':'/workspace','RW':False,'Mode':'ro'}]}
 def test_isolation_metadata_requires_exact_source_instance_and_flags(self):
  oracle=self.oracle();valid=self.metadata()
  # OS ownership is covered by protected live integration; isolate metadata here.
  with patch.object(oracle,'_protected_config_chain'),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps([valid]))):oracle.inspect_candidate_container()
  variants=[]
  for field,value in [('NetworkMode','host'),('ReadonlyRootfs',False),('Privileged',True),('CapAdd',['SYS_ADMIN']),('PidsLimit',999),('PidMode','host'),('IpcMode','host'),('Devices',[{'PathOnHost':'/dev/example'}]),('DeviceRequests',[{'Count':-1}]),('DeviceCgroupRules',['a *:* rwm']),('GroupAdd',['0']),('SecurityOpt',['no-new-privileges=false'])]:
   item=copy.deepcopy(valid);item['HostConfig'][field]=value;variants.append(item)
  item=copy.deepcopy(valid);item['Image']='sha256:'+'e'*64;variants.append(item)
  item=copy.deepcopy(valid);item['Mounts'][0].update(RW=True,Mode='ro');variants.append(item)
  item=copy.deepcopy(valid);item['Config']['Cmd']=['-c','print("7 passed")'];variants.append(item)
  item=copy.deepcopy(valid);item['Mounts'].append({'Type':'tmpfs','Destination':'/usr/local','RW':True});variants.append(item)
  item=copy.deepcopy(valid);item['Config']['Env'].append('LD_PRELOAD=/data/evil.so');variants.append(item)
  for item in variants:
   with self.subTest(item=item),patch.object(oracle,'_protected_config_chain'),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps([item]))),self.assertRaises(ValueError):oracle.inspect_candidate_container()
 def test_invalid_image_deadline_and_loopback_port_are_rejected(self):
  for field,value in [('image','sha256:'),('deadline_at',float('nan')),('deadline_at',time.time()+7200),('api_port','1@other-host')]:
   with self.subTest(field=field),self.assertRaises(ValueError):m.ExternalOracle.validate_config({**self.config,field:value})
 def test_source_tree_change_and_symlink_are_rejected(self):
  original=m.source_tree_hash(self.source);(self.source/'example.py').write_text('value=2\n');self.assertNotEqual(original,m.source_tree_hash(self.source))
  (self.source/'link.py').symlink_to(self.source/'example.py')
  with self.assertRaises(ValueError):m.source_tree_hash(self.source)
 def test_output_cannot_escape_review_scope_or_modify_tested_source(self):
  oracle=self.oracle()
  for directory in [self.root.parent/'outside-protected-scope',self.source/'out']:
   oracle.config['output_dir']=str(directory)
   with self.assertRaises(ValueError):oracle.write_protected_verdict({'verdict':'PASSED'})
 def test_probe_client_is_isolated_and_uses_pinned_instance(self):
  oracle=self.oracle();oracle._container_id='d'*64
  result=self.transport('GET','/health/live',{},None)
  with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(result))) as run:
   oracle.docker_exec_transport('GET','/health/live',{},None)
   argv=run.call_args.args[0];self.assertEqual(argv[2],'d'*64);self.assertEqual(argv[3],'/usr/local/bin/python3');self.assertIn('-I',argv);self.assertIn('-S',argv)

 def admission_transport(self, alteration=None):
  """Scripted API boundary tests controller checks, never scheduler behavior."""
  calls=[];state={'approved':False,'level':4,'missions':[]}
  approval={'id':'approval-first','capability':'process.execute','operation':'Execute task task-first',
            'parameters':{'task_id':'task-first','metadata':{'tool_parameters':{'argv':
             ['/usr/local/bin/python3','-I','-c',backlog.suite_code(delay=18)]}}}}
  if alteration:alteration(approval)
  def transport(method,path,headers,body):
   calls.append((method,path));payload=json.loads(body) if body else None
   if method=='PUT' and path=='/runtime/policy':
    state['level']=payload['level'];value={'mission_budget':{'max_parallel':1}}
   elif method=='POST' and path=='/missions':
    ident='mission-'+str(len(state['missions'])+1);state['missions'].append(ident);value={'id':ident,'version':1}
   elif method=='POST' and path.startswith('/missions/') and path.endswith('/approve'):value={}
   elif method=='POST' and path=='/work-backlog/items':value={'id':'work-'+str(len(state['missions']))}
   elif method=='GET' and path=='/tasks':
    status='completed' if state['level']==5 else ('running' if state['approved'] else 'waiting_approval')
    value=[{'id':'task-first','status':status,'metadata':{'mission_id':state['missions'][0],'approval_id':'approval-first'}}]
    if state['level']==5:value.append({'id':'task-second','status':'completed','metadata':{'mission_id':state['missions'][1]}})
   elif method=='GET' and path=='/security/approvals':value=[approval]
   elif method=='POST' and path=='/security/approvals/approval-first/approve':state['approved']=True;value={}
   elif method=='GET' and path=='/work-backlog':
    value={'items':[{'id':'work-'+str(i+1),'status':'completed' if state['level']==5 else 'ready','evidence':{'tests_run':1}}
                    for i in range(len(state['missions']))]}
   else:raise AssertionError('Unexpected fixture request')
   return {'status':200,'body':base64.b64encode(json.dumps(value).encode()).decode(),'truncated':False}
  return transport,calls

 def test_positive_admission_approves_only_the_exact_fixed_task_before_policy_change(self):
  transport,calls=self.admission_transport()
  oracle=backlog.BacklogOracle(self.path,transport_fn=transport)
  with patch.object(backlog.time,'sleep'):
   oracle.admission()
  approved=calls.index(('POST','/security/approvals/approval-first/approve'))
  self.assertLess(approved,calls.index(('POST','/missions/mission-2/approve')))
  self.assertEqual(calls.count(('POST','/security/approvals/approval-first/approve')),1)
  self.assertEqual(calls.count(('PUT','/runtime/policy')),2)

 def test_positive_admission_rejects_changed_approval_scope_without_approving(self):
  variants=[lambda a:a.update(capability='shell.unrestricted'),
            lambda a:a.update(operation='Execute task another-task'),
            lambda a:a['parameters'].update(task_id='another-task'),
            lambda a:a['parameters']['metadata']['tool_parameters'].update(argv=['sh','-c','different-command'])]
  for change in variants:
   with self.subTest(change=change):
    transport,calls=self.admission_transport(change)
    oracle=backlog.BacklogOracle(self.path,transport_fn=transport)
    with self.assertRaises(AssertionError):oracle.admission()
    self.assertFalse(any(method=='POST' and path.startswith('/security/approvals/') for method,path in calls))
    oracle.lock_file.close()

 def test_positive_probes_reject_truncation_and_non_success_instead_of_reading_candidate_claims(self):
  for status,truncated in [(500,False),(200,True),(403,False)]:
   oracle=backlog.BacklogOracle(self.path,transport_fn=lambda *args:{'status':status,'truncated':truncated,'body':base64.b64encode(b'{"verdict":"PASSED"}').decode()})
   with self.subTest(status=status,truncated=truncated),self.assertRaises(ValueError):oracle.request('GET','/tasks')
   oracle.lock_file.close()
if __name__=='__main__':unittest.main()

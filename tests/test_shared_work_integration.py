import asyncio
from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.runtime.request_service import RequestService
from backend.runtime.durable_automation import DurableAutomations
from backend.runtime.scheduled_runner import ScheduledRunner
from backend.memory.portable_vault import PortableVault,project_identity,clean_text

class NoInference:
 async def chat(self,*args):raise AssertionError('Deterministic automation invoked inference')

@pytest.mark.asyncio
async def test_real_scheduled_request_executes_once_then_exports_answer(tmp_path):
 db=Database(tmp_path/'work.db')
 engine=SimpleNamespace(execution_policy=SimpleNamespace(get=lambda:{'level':4}),events=SimpleNamespace(publish=lambda *a:None),status=lambda:{'running':True},tasks=SimpleNamespace(list=lambda:[]))
 bridge=RequestService(db,engine,NoInference(),None)
 scheduled=DurableAutomations(db,enqueue_request=bridge.create,cancel_request=bridge.cancel)
 item=scheduled.create_work('sample','what time is it',60,mode='auto',enabled=True,autorun=True)
 scheduled.tick();scheduled.deliver()
 runner=ScheduledRunner(scheduled,engine,requests=lambda:bridge)
 await runner.execute_pending(4)
 records=bridge.list('automation-sample','projects/sample')
 assert len(records)==1 and records[0]['status']=='completed'
 await runner.execute_pending(4)
 assert len(bridge.list('automation-sample','projects/sample'))==1
 files=PortableVault(db).export(project_identity('projects/sample'))
 assert len(files)==1 and '# Answer' in next(iter(files.values()))
 assert scheduled.receipts('sample',item['id'])[0]['autorun'] is True

@pytest.mark.asyncio
async def test_queue_only_and_lower_autonomy_never_run_jobs(tmp_path):
 db=Database(tmp_path/'work.db')
 engine=SimpleNamespace(execution_policy=SimpleNamespace(get=lambda:{'level':3}),events=SimpleNamespace(publish=lambda *a:None))
 bridge=RequestService(db,engine,NoInference(),None)
 scheduled=DurableAutomations(db,enqueue_request=bridge.create)
 scheduled.create_work('sample','what time is it',60,mode='auto',enabled=True,autorun=True)
 scheduled.tick();scheduled.deliver()
 await ScheduledRunner(scheduled,engine,requests=lambda:bridge).execute_pending(3)
 assert bridge.list('automation-sample','projects/sample')[0]['status']=='queued'
 # Advancing the schedule clock cannot enqueue over unfinished prior work.
 scheduled.clock=lambda:10**12
 scheduled.tick();scheduled.deliver()
 assert len(bridge.list('automation-sample','projects/sample'))==1

def test_conversation_and_vault_are_project_isolated(tmp_path):
 db=Database(tmp_path/'memory.db');bridge=RequestService(db,None,None,None)
 def body(scope,prompt,key):return dict(project_scope=scope,session_scope='chat',idempotency_key=key,prompt=prompt,mode='quick',model_profile='auto',allow_process=False)
 a=bridge.create(body('one','private apples','a'));bridge.update(a['id'],{'status':'completed','answer':'apple details'})
 b=bridge.create(body('two','private oranges','b'));bridge.update(b['id'],{'status':'completed','answer':'orange details'})
 new=bridge.create(body('one','apples followup','c'))
 messages=bridge.messages(new)
 assert 'apple details' in str(messages) and 'orange details' not in str(messages)
 assert project_identity('one')!=project_identity('two')

def test_trash_revokes_search_and_old_exports_cannot_resurrect(tmp_path):
 vault=PortableVault(Database(tmp_path/'vault.db'))
 doc=vault.put('p','private apples');files=vault.export('p')
 vault.trash('p',doc['id'],1)
 assert vault.search('p','apples')==[] and vault.export('p')=={}
 with pytest.raises(ValueError,match='restore'):vault.import_files('p',files)
 restored=vault.restore('p',doc['id']);assert restored['revision']==2
 with pytest.raises(ValueError):vault.put('p','stale edit',ident=doc['id'],expected_revision=1)
 assert vault.search('p','apples')
 assert 'sk_live_12345678901234567890' not in clean_text('sk_live_12345678901234567890')

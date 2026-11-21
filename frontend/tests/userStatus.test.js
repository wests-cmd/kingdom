import {test} from 'node:test'
import assert from 'node:assert/strict'
import {normalizedTaskStatus, taskStatusInfo, taskCounts, plainLanguageOverview, eventInfo} from '../src/components/common/userStatus.js'

test('task states are plain-language and never imply that a lease or model response proves completion',()=>{
  assert.equal(taskStatusInfo('QUEUED').label, 'Waiting in line')
  assert.match(taskStatusInfo('Leased').explanation, /does not prove execution/)
  assert.match(taskStatusInfo('running').explanation, /not been confirmed/)
  assert.match(taskStatusInfo('completed').next, /verification/)
  assert.match(taskStatusInfo('WAITING_APPROVAL').next, /Review/)
  assert.match(taskStatusInfo('recovery_required').next, /recovery/)
  assert.equal(taskStatusInfo('<script>fake completion</script>').label, 'Status unavailable')
  assert.equal(taskStatusInfo({status:'completed'}).label, 'Status unavailable')
  assert.equal(normalizedTaskStatus(null), '')
})

test('unknown, pending and paused states are not counted as successful results',()=>{
  assert.deepEqual(taskCounts(null), null)
  assert.deepEqual(taskCounts([
    {status:'queued'}, {status:'LEASED'}, {status:'running'},
    {status:'waiting_approval'}, {status:'recovery_required'}, {status:'blocked'},
    {status:'COMPLETED', result:{output:{kind:'model_response', text:'done'}}},
    {status:'FAILED'}, {status:'cancelled'}, {status:'unexpected'}, null
  ]), {queued:1,running:2,approvals:1,recovery:2,completed:1,failed:1,cancelled:1,unknown:2})
})

const base={connection:'LIVE',lastUpdated:'10:02',runtime:{running:true,scheduler_running:true},
  security:{pending_approvals_count:0},tasks:[]}

test('dashboard reports unknown/stale information before trying to recommend controls',()=>{
  assert.match(plainLanguageOverview({...base,lastUpdated:null}).headline, /Getting/)
  const stale=plainLanguageOverview({...base,connection:'OFFLINE',tasks:[{status:'running'}]})
  assert.equal(stale.stale,true)
  assert.match(stale.headline,/may be old/)
  assert.match(stale.explanation,/not current/)
  assert.equal(stale.counts.running,1)
})

test('runtime and scheduler state come from recorded booleans, not task counts',()=>{
  assert.match(plainLanguageOverview({...base,runtime:{running:false},tasks:[{status:'running'}]}).headline,/stopped/)
  assert.match(plainLanguageOverview({...base,runtime:{running:true,scheduler_running:false}}).headline,/needs attention/)
  assert.match(plainLanguageOverview({...base,runtime:{}}).headline,/unavailable/)
  assert.match(plainLanguageOverview({...base,tasks:null}).headline,/unavailable/)
  assert.match(plainLanguageOverview(base).headline,/ready/)
})

test('approval and recovery take priority; queued, leased and running work stay distinct',()=>{
  assert.match(plainLanguageOverview({...base,security:{pending_approvals_count:2},tasks:[{status:'running'}]}).headline,/approval/)
  assert.match(plainLanguageOverview({...base,tasks:[{status:'waiting_approval'}]}).headline,/approval/)
  assert.match(plainLanguageOverview({...base,tasks:[{status:'recovery_required'},{status:'running'}]}).headline,/recovery/)
  assert.match(plainLanguageOverview({...base,tasks:[{status:'leased'}]}).headline,/processing/)
  assert.match(plainLanguageOverview({...base,tasks:[{status:'queued'}]}).headline,/waiting/)
})

test('event explanations distinguish recorded state from proof of external success',()=>{
  assert.match(eventInfo('task.queued').explanation,/not been confirmed/)
  assert.match(eventInfo('task.running').explanation,/not a successful finish/)
  assert.match(eventInfo('task.completed').explanation,/verification/)
  assert.match(eventInfo('governance.approval_required').explanation,/Inspect/)
  assert.equal(eventInfo({event_type:'task.completed'}).title,'Kingdom recorded a system event')
  assert.equal(eventInfo('<script>fake</script>').title,'Kingdom recorded a system event')
})

test('every documented lifecycle state is explained, and preexecution or verification never counts as complete',()=>{
  const states=['CREATED','VALIDATING','WAITING_AUTHORIZATION','WAITING_APPROVAL','AUTHORIZED',
    'APPROVED','QUEUED','LEASED','RUNNING','VERIFYING','SUCCEEDED','COMPLETED','FAILED',
    'CANCEL_REQUESTED','CANCELLED','EXPIRED','BLOCKED','RECOVERY_REQUIRED','UNKNOWN','DENIED']
  for (const state of states) assert.notEqual(taskStatusInfo(state).label,'Status unavailable',state)
  assert.match(taskStatusInfo('WAITING_AUTHORIZATION').explanation,/does not automatically/)
  assert.match(taskStatusInfo('VERIFYING').explanation,/not yet been established/)
  assert.match(taskStatusInfo('EXPIRED').explanation,/Do not assume/)
  const counts=taskCounts(states.map(status=>({status})))
  assert.deepEqual(counts,{queued:6,running:4,approvals:1,recovery:4,completed:2,failed:1,cancelled:1,unknown:1})
})

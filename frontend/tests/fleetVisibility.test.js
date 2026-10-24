import test from 'node:test'
import assert from 'node:assert/strict'
import {peerVisibility,serviceStatus,serviceScope,jobStatus} from '../src/components/common/fleetVisibility.js'
test('stale and revoked work is hidden, not an empty success',()=>{
  for (const state of ['REVOKED','DISCONNECTED','PENDING_APPROVAL']) {
    const result=peerVisibility({node_state:state},{state:'current',activity:{jobs:[{}]},services:{services:[{}]}})
    assert.equal(result.current,false);assert.equal(result.activity,null);assert.equal(result.services,null)
  }
  assert.equal(peerVisibility({node_state:'CONNECTED'},null).reportState,'missing')
})
test('beginner labels distinguish startup, running and acceptance',()=>{
  assert.equal(serviceStatus({state:'stopped',startup:'enabled'}),'Not running · Startup enabled')
  assert.match(serviceScope({scope:'container'}),/unavailable/)
  assert.match(serviceScope({scope:'windows_services'}),/scheduled tasks are not included/)
  assert.equal(jobStatus('completed'),'Recorded complete')
  assert.equal(jobStatus('unrecognized'),'Not reported')
})

test('host observer labels do not claim container startup or control',()=>{
  assert.match(serviceScope({scope:'container',observation_source:'host_report'}),/read-only observer/)
  const label=serviceStatus({id:'docker:kingdom-workshop',state:'running',restart_policy:'unless-stopped',startup:'unknown'})
  assert.equal(label,'Running · Restart unless stopped')
  assert.doesNotMatch(label,/Startup enabled/)
})

import {test} from 'node:test'
import assert from 'node:assert/strict'
import {reviewMeshDestination,retainMeshApproval,meshJoinRequest} from '../src/meshEnrollment.js'

const values=()=>({remote:'https://peer.example',local:'https://self.example',ca:'',confirmed:true,invitation:JSON.stringify({kingdom_id:'peer',kingdom_fingerprint:'fingerprint',invitation_signature:'a'.repeat(128)})})
const response=()=>({approval_id:'b'.repeat(32),authority_endpoint:'https://peer.example',authority_id:'peer',fingerprint:'fingerprint',expires_at:200})

test('joining requires an explicit matching unexpired destination approval',()=>{
  const inputs=values()
  assert.throws(()=>meshJoinRequest(inputs,null,100),/approve/)
  const approval=retainMeshApproval(inputs,response(),100)
  const request=meshJoinRequest(inputs,approval,110)
  assert.equal(request.destination_approval_id,'b'.repeat(32))
  assert.equal(request.authority_endpoint,'https://peer.example')
  assert.equal(request.local_endpoint,inputs.local)
  assert.throws(()=>meshJoinRequest(inputs,approval,200),/approve/)
  for(const key of ['remote','local','invitation','ca']) assert.throws(()=>meshJoinRequest({...inputs,[key]:inputs[key]+'x'},approval,110),/approve/)
  // A delayed approval response cannot authorize a subsequently unchecked form.
  assert.throws(()=>meshJoinRequest({...inputs,confirmed:false},approval,110),/approve/)
  assert.throws(()=>retainMeshApproval({...inputs,confirmed:false},response(),100),/Confirm trust/)
})

test('authority display and request reject legacy or redirected-looking inputs',()=>{
  for(const remote of ['https://peer.example/path','https://u:p@peer.example','https://peer.example/?redirect=internal','http://private.example'])
    assert.throws(()=>reviewMeshDestination({...values(),remote}))
  assert.equal(reviewMeshDestination({...values(),remote:'http://127.0.0.1:8000'}).authority_endpoint,'http://127.0.0.1:8000')
  assert.throws(()=>reviewMeshDestination({...values(),invitation:'{}'}),/signed invitation/)
  assert.throws(()=>retainMeshApproval(values(),{...response(),authority_id:'different'},100),/does not match/)
  assert.throws(()=>retainMeshApproval(values(),{...response(),expires_at:9999},100),/does not match/)
})

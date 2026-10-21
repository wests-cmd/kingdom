import {test} from 'node:test'
import assert from 'node:assert/strict'
import {deviceLabel,capabilityLabel,fingerprintLabel,nodeStateLabel,workerLabel,apprenticeLabel} from '../src/components/common/presentation.js'

test('untrusted worker source and internal records are never ordinary labels',()=>{
 for(const value of ['def execute(): return secret','import os','{"token":"secret"}','<script>alert(1)</script>',{code:'source'},null]) {
  assert.equal(deviceLabel(value),'Registered device')
  assert.equal(workerLabel(value),'Registered worker')
  assert.equal(capabilityLabel(value),'Unsupported capability metadata')
  assert.equal(nodeStateLabel(value),'Unknown')
 }
 assert.equal(deviceLabel('Research PC'),'Research PC')
 assert.equal(capabilityLabel('memory.read'),'memory read')
 assert.equal(fingerprintLabel('a'.repeat(64)),'a'.repeat(64))
 assert.equal(fingerprintLabel('private-key'),'No verified fingerprint recorded')
})

test('public Apprentice labels preserve legacy routing IDs without calling agents computers',()=>{
 assert.equal(apprenticeLabel({id:'knight-coder'}),'Apprentices-coder')
 assert.equal(apprenticeLabel({id:'KG-peer/knight-researcher'}),'Apprentices-researcher')
 assert.equal(apprenticeLabel({public_id:'Apprentices-planner'}),'Apprentices-planner')
 assert.equal(apprenticeLabel({role:'memory'}),'Apprentices-memory')
 assert.equal(apprenticeLabel({id:'<script>bad</script>'}),'Registered Apprentice')
 assert.equal(apprenticeLabel(null),'Registered Apprentice')
})

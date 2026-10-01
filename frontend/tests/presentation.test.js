import {test} from 'node:test'
import assert from 'node:assert/strict'
import {deviceLabel,capabilityLabel,fingerprintLabel,nodeStateLabel,workerLabel} from '../src/components/common/presentation.js'

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

import {test} from 'node:test'
import assert from 'node:assert/strict'
import {taskEvidenceRecords,analysisSummary} from '../src/components/common/taskEvidence.js'

test('actual remote envelope displays controller-verified analysis and preserves executor',()=>{
  const result={output:{kind:'native_tool',tool:'text.analyze@1.0.0',output:{words:2,characters:11}},verification:{state:'VERIFIED'},executed_by:'worker-2'}
  const records=taskEvidenceRecords(result)
  assert.equal(records.length,1)
  assert.equal(records[0].executed_by,'worker-2')
  assert.equal(analysisSummary(records[0]),'Verified text analysis: 2 words; 11 characters.')
})

test('worker assertions and process success cannot impersonate controller verification',()=>{
  for(const verification of [undefined,{state:'UNVERIFIED'},{state:'FAILED'}]) {
    const records=taskEvidenceRecords({output:{kind:'native_tool',tool:'text.analyze@1.0.0',verified:true,output:{words:1,characters:4,exit_code:0,verification:{state:'VERIFIED'}}},verification})
    assert.equal(analysisSummary(records[0]),'Unverified text analysis: 1 words; 4 characters.')
  }
  const python={outcome:{tool:'code.python.analyze@1.0.0',output:{valid_python:true}}}
  assert.match(analysisSummary(python),/^Syntax has not been verified/)
  assert.match(analysisSummary({...python,verification:{state:'VERIFIED'}}),/^Python syntax verified/)
})

test('local results remain supported and unknown envelopes stay unsupported',()=>{
  const local=[{outcome:{tool:'text.analyze@1.0.0',output:{words:0,characters:0}},verification:{state:'VERIFIED'}}]
  assert.equal(taskEvidenceRecords({results:local}),local)
  assert.equal(analysisSummary(local[0]),'Verified text analysis: 0 words; 0 characters.')
  assert.deepEqual(taskEvidenceRecords({output:{tool:'text.analyze@1.0.0'},verification:{state:'VERIFIED'}}),[])
})

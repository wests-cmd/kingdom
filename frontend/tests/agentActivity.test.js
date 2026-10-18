import {test} from 'node:test'
import assert from 'node:assert/strict'
import {activityStages,formatWait} from '../src/components/common/agentActivity.js'

test('a completed model response cannot paint tool execution or tests as verified',()=>{
 const stages=activityStages({status:'completed',turns:1,verified_actions:0,independent_tests_verified:false})
 assert.equal(stages[1].state,'received')
 assert.equal(stages[2].state,'not verified')
 assert.equal(stages[3].state,'not verified')
})
test('tool receipts still do not imply independent code tests',()=>{
 const stages=activityStages({status:'completed',turns:3,verified_actions:2,independent_tests_verified:false})
 assert.equal(stages[2].state,'receipts available')
 assert.equal(stages[3].state,'not verified')
})
test('waiting is labelled as waiting instead of invented completion percentages',()=>{
 const stages=activityStages({status:'thinking',turns:0,verified_actions:0,independent_tests_verified:false})
 assert.equal(stages[1].state,'waiting')
 assert.equal(formatWait(91),'1m 31s')
 assert.equal(formatWait(-10),'0s')
})

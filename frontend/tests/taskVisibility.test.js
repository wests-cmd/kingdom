import test from 'node:test'
import assert from 'node:assert/strict'
import {taskChangeReport,notificationItems,healthSummary,safeRecordedTime} from '../src/components/common/taskVisibility.js'

test('changes only reflect verified recorded workspace/build receipts',()=>{
 const task={status:'completed',result:{results:[
  {outcome:{kind:'model_response',tool:'workspace.write@1.0.0',output:{path:'not-proven.py'}},verification:{state:'UNVERIFIED'}},
  {outcome:{tool:'workspace.write@1.0.0',output:{path:'docs/report.md'}},verification:{state:'VERIFIED'}},
  {outcome:{tool:'process.run@1.0.0',output:{exit_code:0}},verification:{state:'VERIFIED'}},
  {outcome:{tool:'build.run@1.0.0',output:{artifacts:{'out.bin':{sha256:'a'.repeat(64)}}}},verification:{state:'VERIFIED'}},
  {outcome:{kind:'model_response',output:{text:'all tests passed'}}}
 ]}}
 const report=taskChangeReport(task)
 assert.equal(report.lines.length,3)
 assert.ok(report.lines.some(x=>x.detail==='docs/report.md'))
 assert.ok(report.lines.some(x=>x.detail==='0'))
 assert.ok(report.lines.some(x=>x.detail==='out.bin'))
 assert.ok(report.lines.every(x=>!x.detail.includes('not-proven')))
 assert.match(report.notice,/not a Git diff/)
})

test('spoofed verified model prose is never a file change receipt',()=>{
 const report=taskChangeReport({status:'completed',result:{results:[
  {outcome:{kind:'model_response',tool:'workspace.write@1.0.0',output:{path:'fake-file.py'}},verification:{state:'VERIFIED'}}
 ]}})
 assert.equal(report.lines.length,0)
})

test('a model reply alone cannot say files were changed',()=>{
 const report=taskChangeReport({status:'completed',result:{results:[
  {outcome:{kind:'model_response',output:{text:'I edited a secret'}},verification:{state:'VERIFIED'}}
 ]}})
 assert.equal(report.lines.length,0)
 assert.match(report.notice,/No independently verified/)
})

test('notifications omit payloads, secrets, unknown event kinds and duplicates',()=>{
 const records=[
  {event_id:'1',event_type:'task.failed',timestamp:1730000000,task_id:'safe-task',payload:{password:'SECRET'}},
  {event_id:'1',event_type:'task.failed',timestamp:1730000000,payload:{password:'SECRET'}},
  {event_id:'2',event_type:'task.completed',timestamp:'2026-11-21T20:00:00Z',data:{token:'SECRET'}},
  {event_id:'3',event_type:'unknown_event',timestamp:1730000002,payload:{password:'SECRET'}}
 ]
 const notices=notificationItems(records)
 assert.equal(notices.length,2)
 assert.deepEqual(notices.map(x=>x.id),['2','1'])
 assert.ok(notices.every(x=>!JSON.stringify(x).includes('SECRET')))
 assert.equal(notices[1].important,true)
 assert.equal(notices[1].taskId,'safe-task')
 assert.equal(notificationItems(null),null)
})

test('a health source failure remains unknown, rather than treated as zero',()=>{
 const none=healthSummary({})
 assert.equal(none.cpuCores,null)
 assert.equal(none.connectedPeers,null)
 assert.equal(none.configuredModels,null)
 const known=healthSummary({
  hardware:{cpu_cores:2,memory_available_gb:1.32,disk_free_gb:48.2},
  orchestration:{counts:{connected_peers:1,paired_knights:3},inventory:{complete:false}},
  models:{profiles:[{id:'x'},{id:'y'}]}
 })
 assert.equal(known.cpuCores,2)
 assert.equal(known.availableRamGB,1.32)
 assert.equal(known.connectedPeers,1)
 assert.equal(known.pairedPeers,3)
 assert.equal(known.inventoryComplete,false)
 assert.equal(known.configuredModels,2)
 assert.equal(safeRecordedTime(null),'Time unavailable')
})

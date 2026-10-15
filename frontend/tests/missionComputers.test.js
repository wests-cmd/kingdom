import {test} from 'node:test'
import assert from 'node:assert/strict'
import {eligibleMissionComputers,setStepComputer,canChooseComputer} from '../src/components/missionComputers.js'

test('mission targets require approved paired computers with actual compute grants',()=>{
 const approved={id:'approved',node_state:'APPROVED',granted_capabilities:['compute']}
 const connected={...approved,id:'connected',node_state:'CONNECTED'}
 const nodes=[approved,connected,{...approved,id:'local',is_local:true},{...approved,id:'revoked',node_state:'REVOKED'},{...approved,id:'requested',granted_capabilities:[],capabilities:['compute']},{...approved,id:'pending',node_state:'PENDING_APPROVAL'}]
 assert.deepEqual(eligibleMissionComputers(nodes).map(node=>node.id),['approved','connected'])
 assert.deepEqual(eligibleMissionComputers(null),[])
})

test('selecting default removes required target without altering other mission fields',()=>{
 const step={id:'syntax',kind:'python_check',computer_id:'worker',depends_on:['source'],instructions:'Check source'}
 assert.deepEqual(setStepComputer(step,''),{id:'syntax',kind:'python_check',depends_on:['source'],instructions:'Check source'})
 assert.equal(step.computer_id,'worker')
 assert.equal(setStepComputer({...step,kind:'text_check'},'worker-2').computer_id,'worker-2')
 const unsupported={...step,kind:'process'}
 assert.equal(canChooseComputer(unsupported),false)
 assert.equal(setStepComputer(unsupported,''),unsupported)
})

test('build placement requires an actual process grant rather than compute',()=>{
 const nodes=[{id:'analysis',node_state:'CONNECTED',granted_capabilities:['compute']},{id:'build',node_state:'CONNECTED',granted_capabilities:['process.execute']}]
 assert.deepEqual(eligibleMissionComputers(nodes,'build').map(n=>n.id),['build'])
 assert.equal(canChooseComputer({kind:'build'}),true)
})

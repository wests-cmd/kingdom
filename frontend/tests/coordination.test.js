import {test} from 'node:test'
import assert from 'node:assert/strict'
import {coordinationPage, coordinationDepths, coordinatorOptions} from '../src/components/common/coordination.js'

const nodes=Array.from({length:1000},(_,i)=>({id:`pc${i}`,label:`Computer ${i}`}))
test('large clusters keep visible participants and parent options bounded',()=>{
 assert.equal(coordinationPage(nodes,0).nodes.length,20)
 assert.equal(coordinationPage(nodes,999).page,49)
 assert.equal(coordinationPage(nodes,999).nodes.at(-1).id,'pc999')
 assert.equal(coordinationPage([],7).pages,1)
 const options=coordinatorOptions(nodes,'pc0','','pc999')
 assert.equal(options.total,999)
 assert.equal(options.nodes.length,51)
 assert.equal(options.nodes[0].id,'pc999')
 assert.ok(!options.nodes.some(n=>n.id==='pc0'))
 assert.deepEqual(coordinatorOptions(nodes,'pc0','Computer 987','kingdom').nodes.map(n=>n.id),['pc987'])
})
test('deep reporting chains retain true levels without recursive stack growth',()=>{
 const parents=Object.fromEntries(nodes.map((n,i)=>[n.id,i?`pc${i-1}`:'kingdom']))
 const depths=coordinationDepths(nodes.toReversed(),parents)
 assert.equal(depths.get('pc0'),1)
 assert.equal(depths.get('pc999'),1000)
 assert.equal(depths.get('kingdom'),0)
})

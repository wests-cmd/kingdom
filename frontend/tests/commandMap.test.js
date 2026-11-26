import test from 'node:test'
import assert from 'node:assert/strict'
import {mapNodes,pageNodes,geometry,history,commit,undo,redo,moveCard,moveFrame,resizeFrame,connectionState,metrics,knightKey,agentKey} from '../src/components/common/commandMap.js'
const computers=[{id:'local',name:'Controller'},{id:'a',name:'Laptop',state:'CONNECTED',current:true},{id:'b',name:'Worker',state:'CONNECTED',current:false}]
const groups=[{id:'g',name:'Engineering',captain:'a',members:['a','b']}]
const topology={nodes:[{id:'a/coder',kind:'apprentice',label:'Coder',host:'a'},{id:'b/tester',kind:'apprentice',label:'Tester',host:'b'}],parents:{'a/coder':'a'}}

test('only known computers and current hosted Apprentices appear; layout cannot resurrect stale identities',()=>{
 const nodes=mapNodes(computers,groups,topology,'teams')
 assert.ok(nodes.some(n=>n.key===agentKey('a/coder')))
 assert.ok(!nodes.some(n=>n.key===agentKey('b/tester')))
 assert.equal(mapNodes(computers,groups,topology,'network').length,3)
 const layout=geometry(nodes,groups,{'knight:removed':{x:3,y:3}})
 assert.equal(Object.keys(layout.boxes).length,4)
 assert.equal(layout.boxes['knight:removed'],undefined)
})

test('visual drag and resizing never change organization; undo/redo are bounded drafts',()=>{
 const source=JSON.stringify(groups)
 const nodes=mapNodes(computers,groups,topology,'teams')
 const layout=geometry(nodes,groups,{})
 const group=layout.frames.find(f=>f.id==='g')
 const moved=moveFrame({},group,layout.boxes,48,32)
 assert.equal(moved[knightKey('a')].x,layout.boxes[knightKey('a')].x+48)
 const resized=resizeFrame(moved,group,1200,700)
 assert.equal(geometry(nodes,groups,resized).frames.find(f=>f.id==='g').w,1200)
 let h=commit(history(),moved)
 h=commit(h,resized)
 assert.deepEqual(undo(h).doc,moved)
 assert.deepEqual(redo(undo(h)).doc,resized)
 assert.equal(JSON.stringify(groups),source)
 for(let i=0;i<60;i++)h=commit(h,moveCard(h.doc,knightKey('local'),{x:16*i,y:0}))
 assert.ok(h.past.length<=40)
})

test('positions persist across changed status and filtering; bounds and missing metrics are honest',()=>{
 const original=mapNodes(computers,groups,topology,'network')
 const saved=moveCard({},knightKey('a'),{x:141,y:200})
 assert.equal(geometry(original,groups,saved).boxes[knightKey('a')].x,144)
 const filtered=pageNodes(mapNodes(computers.map(c=>({...c,current:false})),groups,topology,'network'),'laptop',0)
 assert.equal(geometry(filtered.nodes,groups,saved).boxes[knightKey('a')].x,144)
 assert.equal(connectionState(computers[2]),'unknown')
 assert.equal(connectionState({...computers[1],state:'REVOKED'}),'problem')
 assert.equal(metrics(undefined),null);assert.equal(metrics(true),null);assert.equal(metrics(0),0)
 const many=mapNodes(Array.from({length:100},(_,i)=>({id:String(i),name:String(i)})),[],null,'network')
 assert.equal(pageNodes(many,'',0).nodes.length,40)
 assert.equal(pageNodes(many,'',99).nodes.length,20)
})

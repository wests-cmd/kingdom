import assert from 'node:assert/strict'
import {graphLayout,releaseIntent,W,H} from './proximityGraph.js'
const computers=Array.from({length:25},(_,i)=>({id:String(i)}))
const groups=[{id:'a',name:'A',members:['0','1']},{id:'b',name:'B',members:['2','3']}]
const {points}=graphLayout(computers,groups)
assert.equal(Object.keys(points).length,25)
for(const p of Object.values(points))assert.ok(Number.isFinite(p.x)&&p.x>0&&p.x<W&&p.y>0&&p.y<H)
assert.deepEqual(graphLayout(computers,groups),graphLayout(computers,groups))
assert.deepEqual(releaseIntent('4',{x:90,y:90},{4:{x:400,y:400},5:{x:100,y:100}},[]),{kind:'create',members:['4','5']})
assert.deepEqual(releaseIntent('4',{x:90,y:90},{4:{x:400,y:400},0:{x:100,y:100}},groups),{kind:'add',group:'a',members:['4']})
assert.deepEqual(releaseIntent('0',{x:90,y:90},{0:{x:400,y:400},2:{x:100,y:100}},groups),{kind:'combine',groups:['a','b']})
assert.equal(releaseIntent('0',{x:90,y:90},{0:{x:400,y:400},1:{x:100,y:100}},groups),null)
assert.deepEqual(releaseIntent('0',{x:900,y:400},{0:{x:900,y:400},1:{x:100,y:100}},groups),{kind:'remove',members:['0']})
assert.equal(releaseIntent('4',{x:900,y:400},{4:{x:900,y:400},1:{x:100,y:100}},groups),null)
assert.equal(graphLayout([],[]).regions.length,0)
console.log('Proximity graph: layout, merge/add/remove proposals, same-group protection and empty state passed')

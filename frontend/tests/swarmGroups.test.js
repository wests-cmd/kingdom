import test from 'node:test'
import assert from 'node:assert/strict'
import {memberChoices,splitSizes,swarmCount} from '../src/components/common/swarmGroups.js'

test('other-team Knights are gray candidates at the bottom, and selections remain checked',()=>{
 const computers=[{id:'a',name:'A'},{id:'b',name:'B'},{id:'c',name:'C'}]
 const groups=[{id:'first',name:'First',members:['a']},{id:'second',name:'Second',members:['b']}]
 const choices=memberChoices(computers,groups,'first',['a','b'])
 assert.deepEqual(choices.map(c=>c.id),['a','c','b'])
 assert.equal(choices[0].checked,true)
 assert.equal(choices[2].other.name,'Second')
 assert.equal(choices[2].checked,true)
 assert.equal(choices[1].other,undefined)
})
test('uneven splits give the extra members to the first groups',()=>{
 assert.deepEqual(splitSizes(5,2),[3,2])
 assert.deepEqual(splitSizes(7,3),[3,2,2])
 assert.deepEqual(splitSizes(2,3),[])
 assert.deepEqual(splitSizes(2,2),[1,1])
})
test('one Kingdom contains multiple Knights instead of counting computers as Kingdoms',()=>{
 assert.equal(swarmCount([{}]),'One Kingdom · 1 Knight')
 assert.equal(swarmCount([{}, {}, {}, {}]),'One Kingdom · 4 Knights')
})

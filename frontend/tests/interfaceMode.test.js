import {test} from 'node:test'
import assert from 'node:assert/strict'
import {loadInterfaceMode,saveInterfaceMode,navigationForMode,pageForMode,INTERFACE_MODE_KEY} from '../src/interfaceMode.js'

test('workspace view persists and unavailable storage still permits a session change',()=>{
 const saved=new Map(),storage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)}
 assert.equal(loadInterfaceMode(storage),'easy')
 assert.equal(saveInterfaceMode(storage,'advanced'),true)
 assert.equal(saved.get(INTERFACE_MODE_KEY),'advanced')
 assert.equal(loadInterfaceMode(storage),'advanced')
 assert.equal(saveInterfaceMode(storage,'easy'),true)
 assert.equal(loadInterfaceMode(storage),'easy')
 assert.equal(loadInterfaceMode({getItem:()=>'<script>'}),'easy')
 assert.equal(loadInterfaceMode({getItem:()=>{throw Error('blocked')}}),'easy')
 assert.equal(saveInterfaceMode({setItem:()=>{throw Error('blocked')}},'advanced'),false)
})
test('easy navigation is smaller while retaining approvals, computers and recovery',()=>{
 const easy=navigationForMode('easy').flatMap(group=>group.items.map(item=>item[0]))
 const advanced=navigationForMode('advanced').flatMap(group=>group.items.map(item=>item[0]))
 assert.ok(easy.length<advanced.length)
 for(const required of ['Workbench','Tasks','Nodes','Governance','Security','Recovery'])assert.ok(easy.includes(required))
 assert.ok(!easy.includes('Routing'))
 assert.ok(advanced.includes('Routing'))
 assert.equal(pageForMode('Routing','easy'),'Dashboard')
 assert.equal(pageForMode('Nodes','easy'),'Nodes')
 assert.equal(pageForMode('Routing','advanced'),'Routing')
})

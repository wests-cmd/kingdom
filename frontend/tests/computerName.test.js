import test from 'node:test'
import assert from 'node:assert/strict'
import {computerName} from '../src/components/common/computerName.js'

test('username and computer remain consistent regardless of list position',()=>{
 assert.equal(computerName('bot1','Laptop 2','id-a'),'bot1 · Laptop 2')
 assert.equal(computerName('bot2','Laptop 3','id-b'),'bot2 · Laptop 3')
 assert.equal(computerName('bot1','bot1','id-a'),'bot1')
})
test('unknown names use a distinguishing identity instead of kingdom-node',()=>{
 assert.equal(computerName(null,'kingdom-node','KG-12345678'),'Computer 12345678')
 assert.equal(computerName(null,'host','id'),'host')
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { RealtimeClient } from '../src/common/realtimeClient.js'

function fixture() {
  const sockets = [], timers = new Map()
  let id = 0
  const clock = {
    setTimeout(fn) { timers.set(++id, fn); return id },
    clearTimeout(key) { timers.delete(key) }
  }
  const client = new RealtimeClient(() => {
    const socket = { closed: false, close() { this.closed = true } }
    sockets.push(socket)
    return socket
  }, clock)
  const tick = () => {
    const callbacks = [...timers.values()]
    timers.clear()
    callbacks.forEach(fn => fn())
  }
  return {client, sockets, timers, tick}
}

test('one socket and retry; disconnect stops reconnect and obsolete events', () => {
  const {client, sockets, timers, tick} = fixture()
  const statuses = [], messages = []
  client.onStatusChange(s => statuses.push(s))
  client.onEvent(m => messages.push(m))
  client.connect()
  client.connect()
  assert.equal(sockets.length, 1)
  const first = sockets[0]
  first.onopen()
  const oldMessage = first.onmessage
  const oldClose = first.onclose
  oldClose()
  oldClose()
  client.connect()
  assert.equal(timers.size, 1)
  tick()
  assert.equal(sockets.length, 2)
  oldMessage({data: '{"old":true}'})
  oldClose()
  assert.equal(timers.size, 0)
  sockets[1].onopen()
  sockets[1].onmessage({data: '{"current":true}'})
  client.disconnect()
  assert.equal(sockets[1].closed, true)
  assert.deepEqual(messages, [{current:true}])
  assert.deepEqual(statuses, [false,true,false,true,false])
  tick()
  assert.equal(sockets.length, 2)
})

test('disconnect cancels a pending retry', () => {
  const {client, sockets, timers, tick} = fixture()
  client.connect()
  sockets[0].onclose()
  assert.equal(timers.size, 1)
  client.disconnect()
  assert.equal(timers.size, 0)
  tick()
  assert.equal(sockets.length, 1)
})

test('a failing observer or malformed event cannot block another view', () => {
  const {client, sockets} = fixture()
  const received = []
  client.onEvent(() => { throw Error('view failure') })
  client.onEvent(data => received.push(data))
  client.connect()
  sockets[0].onmessage({data: 'not json'})
  sockets[0].onmessage({data: '{"type":"runtime.snapshot"}'})
  assert.deepEqual(received, [{type:'runtime.snapshot'}])
})

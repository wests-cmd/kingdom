import test from 'node:test'
import assert from 'node:assert/strict'
import { startPolling } from '../src/common/polling.js'

test('hidden UI slows to one minute; returning refreshes immediately and cleanup stops it', async () => {
  let handler, callback, delay, loads = 0, removed = false
  const page = {hidden:false,addEventListener:(_,fn)=>{handler=fn},removeEventListener:()=>{removed=true}}
  const clock = {setTimeout:(fn,ms)=>{callback=fn;delay=ms;return 1},clearTimeout:()=>{callback=null}}
  const stop = startPolling(async()=>{loads++},3000,page,clock)
  await Promise.resolve()
  assert.equal(loads,1);assert.equal(delay,3000)
  page.hidden=true;handler();assert.equal(delay,60000)
  await callback();assert.equal(loads,2);assert.equal(delay,60000)
  page.hidden=false;handler();await Promise.resolve();assert.equal(loads,3);assert.equal(delay,3000)
  stop();assert.equal(callback,null);assert.equal(removed,true)
})

test('slow polls cannot overlap, visibility events cannot duplicate the in-flight request', async () => {
  let release, handler, calls=0, scheduled=0
  const page={hidden:false,addEventListener:(_,fn)=>{handler=fn},removeEventListener:()=>{}}
  const clock={setTimeout:()=>{scheduled++;return 1},clearTimeout:()=>{}}
  const stop=startPolling(()=>{calls++;return new Promise(resolve=>{release=resolve})},5000,page,clock)
  handler();handler();assert.equal(calls,1);assert.equal(scheduled,0)
  stop();release();await Promise.resolve();await Promise.resolve();assert.equal(scheduled,0)
})

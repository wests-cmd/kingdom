import test from 'node:test'
import assert from 'node:assert/strict'
import {parallelChatRequest} from '../src/utils/parallelChatRequest.js'

test('automatic chat can route to native Ollama without incompatible reasoning options',()=>{
  const messages=[{role:'user',content:'What can you prove?'}]
  const request=parallelChatRequest(messages)
  assert.equal(Object.hasOwn(request,'reasoning_effort'),false)
  assert.equal(Object.hasOwn(request,'think'),false)
  assert.deepEqual(request.messages,messages)
  assert.equal(request.stream,false)
  assert.equal(request.max_tokens,1024)
})

import {test, after} from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import {createServer} from 'vite'
import {fileURLToPath} from 'node:url'

const server = await createServer({root:fileURLToPath(new URL('..',import.meta.url)),
  server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'})
after(()=>server.close())
const {default:Status} = await server.ssrLoadModule('/src/components/BluetoothStatusView.jsx')
const render = props => renderToStaticMarkup(React.createElement(Status,{onRefresh:()=>{},...props}))
const base = {platform:'Linux',observed_at:100,adapters:[],pan_links:[],available:false,adapter_state:'absent',reason:'No adapter exposed'}

test('loading and errors do not claim a working link or retain old readiness',()=>{
  assert.match(render({loading:true}),/Checking Bluetooth/)
  const error=render({data:{...base,adapter_state:'on',pan_links:[{interface:'bnep0'}]},error:'offline'})
  assert.match(error,/role="alert"/)
  assert.match(error,/status unavailable/)
  assert.doesNotMatch(error,/PAN link connected|bnep0/)
})

test('absent, off and powered without PAN have explicit beginner labels',()=>{
  assert.match(render({data:base}),/No usable Bluetooth adapter reported/)
  assert.match(render({data:{...base,adapter_state:'off'}}),/Bluetooth is off/)
  assert.match(render({data:{...base,adapter_state:'on'}}),/Bluetooth is on · No PAN connection/)
})

test('a real PAN report stays distinct from a verified peer route or task routing',()=>{
  const html=render({data:{...base,adapter_state:'on',available:true,pan_links:[{interface:'bnep0',device_address:'AA:BB'}]}})
  assert.match(html,/PAN link connected/)
  assert.match(html,/Peer route: not checked/)
  assert.match(html,/Only this Knight/)
  assert.match(html,/no task routing or automatic pairing is enabled/)
  assert.doesNotMatch(html,/route verified|ready to execute/i)
})

test('adapter and interface labels render as escaped React text',()=>{
  const html=render({data:{...base,adapter_state:'on',reason:'<script>bad()</script>',adapters:[{path:'one',address:'<img src=x onerror=bad()>',powered:true}],pan_links:[{interface:'<svg onload=bad()>',device_address:'AA'}]}})
  assert.match(html,/&lt;script&gt;/)
  assert.match(html,/&lt;img/)
  assert.match(html,/&lt;svg/)
  assert.doesNotMatch(html,/<script|<img|<svg/)
})

test('manual refresh is disabled during loading or an existing request',()=>{
  assert.match(render({loading:true}),/<button[^>]*disabled/)
  const busy=render({data:base,busy:true})
  assert.match(busy,/<button[^>]*disabled/)
  assert.match(busy,/Refreshing…/)
  assert.doesNotMatch(render({data:base}),/<button[^>]*disabled/)
})

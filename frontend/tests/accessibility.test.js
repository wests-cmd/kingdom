import {test} from 'node:test'
import assert from 'node:assert/strict'
import {DEFAULT_APPEARANCE,appearanceVariables,contrastRatio,loadAppearance,sanitizeAppearance,saveAppearance} from '../src/appearance.js'

test('accessibility settings survive reload without accepting injected CSS or changing unrelated appearance',()=>{
 const data=new Map(),storage={getItem:key=>data.get(key),setItem:(key,value)=>data.set(key,value)}
 const selected={...DEFAULT_APPEARANCE,scale:200,contrast:'high',targets:'large',focus:'strong',reading:'spacious',pointer:'large',distraction:'quiet'}
 assert.equal(saveAppearance(storage,selected),true)
 assert.deepEqual(loadAppearance(storage),selected)
 assert.equal(sanitizeAppearance({...selected,contrast:'url(evil)',scale:500}).contrast,'standard')
 assert.equal(sanitizeAppearance({...selected,contrast:'url(evil)',scale:500}).scale,100)
 assert.equal(loadAppearance({getItem:()=>JSON.stringify({scale:125,motion:'reduced'})}).targets,'standard')
})
test('high contrast and quiet modes remove decoration and retain legible text in either theme',()=>{
 for(const mode of ['dark','light']){
  const {variables}=appearanceVariables({...DEFAULT_APPEARANCE,mode,contrast:'high'})
  assert.equal(variables['--atmosphere-opacity'],'0')
  assert.ok(contrastRatio(variables['--text-main'],variables['--surface-dark'])>=7)
  assert.ok(contrastRatio(variables['--text-muted'],variables['--surface-dark'])>=7)
 }
 assert.equal(appearanceVariables({...DEFAULT_APPEARANCE,distraction:'quiet',atmosphere:20}).variables['--atmosphere-opacity'],'0')
})

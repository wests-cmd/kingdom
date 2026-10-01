import {test} from 'node:test'
import assert from 'node:assert/strict'
import {APPEARANCE_KEY,DEFAULT_APPEARANCE,appearanceVariables,contrastRatio,loadAppearance,readableAccent,sanitizeAppearance,saveAppearance} from '../src/appearance.js'

test('saved appearance rejects CSS injection, unknown options and invalid sizes',()=>{
  const data=sanitizeAppearance({accent:'red; background:url(https://evil.example)',mode:'anything',density:'other',scale:999,motion:'unsafe',atmosphere:100,palette:'__proto__'})
  assert.deepEqual(data,DEFAULT_APPEARANCE)
  assert.deepEqual(loadAppearance({getItem:()=>'{invalid'}),DEFAULT_APPEARANCE)
  assert.deepEqual(loadAppearance({getItem:()=>{throw Error('blocked')}}),DEFAULT_APPEARANCE)
})
test('appearance persists selected colors and survives unavailable storage honestly',()=>{
  const values=new Map()
  const storage={getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)}
  const selected={...DEFAULT_APPEARANCE,accent:'#123456',mode:'light',scale:125,density:'compact',motion:'reduced',atmosphere:0}
  assert.equal(saveAppearance(storage,selected),true)
  assert.ok(values.has(APPEARANCE_KEY))
  assert.deepEqual(loadAppearance(storage),selected)
  assert.equal(saveAppearance({setItem:()=>{throw Error('quota')}},selected),false)
})
test('custom accent text remains readable in either mode and retains semantic status colors',()=>{
  for(const mode of ['dark','light'])for(const accent of ['#000000','#ffffff','#123456','#b69aff','#f00000','#00ffff']){
    const {variables}=appearanceVariables({...DEFAULT_APPEARANCE,mode,accent})
    for(const background of ['--surface-dark','--bg-dark','--sidebar-bg','--input-bg','--button-bg'])assert.ok(contrastRatio(variables['--accent-readable'],variables[background])>=4.5)
    assert.ok(contrastRatio(accent,variables['--accent-on-primary'])>=4.5)
    assert.notEqual(variables['--accent-green'],accent)
  }
  assert.equal(appearanceVariables({...DEFAULT_APPEARANCE,mode:'system'},false).dark,false)
  assert.equal(appearanceVariables({...DEFAULT_APPEARANCE,mode:'system'},true).dark,true)
})

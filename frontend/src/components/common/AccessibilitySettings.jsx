import React from 'react'
import {useAppearance} from './AppearanceProvider'

const options={contrast:[['standard','Standard'],['high','High contrast']],targets:[['standard','Standard'],['large','Large controls']],focus:[['standard','Standard'],['strong','Strong outline']],pointer:[['standard','Standard'],['large','Large pointer']],reading:[['standard','Standard'],['spacious','Extra reading space']],distraction:[['standard','Standard'],['quiet','Less distraction']]}
const labels={contrast:'Contrast',targets:'Control size',focus:'Keyboard focus',pointer:'Pointer',reading:'Reading space',distraction:'Distraction level'}
const presets=[
 ['Larger and clearer',{scale:150,contrast:'high',targets:'large',focus:'strong',atmosphere:0}],
 ['Keyboard friendly',{targets:'large',focus:'strong',motion:'reduced'}],
 ['Reading comfort',{reading:'spacious',targets:'large',focus:'strong'}],
 ['Less distraction',{distraction:'quiet',motion:'reduced',atmosphere:0}],
]
export default function AccessibilitySettings(){
 const {settings,update}=useAppearance()
 return <section className="panel" aria-labelledby="accessibility-title">
  <h2 id="accessibility-title">Accessibility</h2>
  <p>Choose what makes Kingdom easier to use. No diagnosis is needed. You can customize every option.</p>
  <div className="action-row" aria-label="Accessibility starting points">{presets.map(([name,changes])=><button key={name} onClick={()=>update(changes)}>{name}</button>)}</div>
  <div className="appearance-fields">{Object.entries(options).map(([key,values])=><label key={key}>{labels[key]}<select id={`accessibility-${key}`} value={settings[key]} onChange={event=>update({[key]:event.target.value})}>{values.map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label>)}
  <label>Interface size<select id="accessibility-scale" value={settings.scale} onChange={event=>update({scale:Number(event.target.value)})}>{[90,100,110,125,150,175,200].map(value=><option key={value} value={value}>{value}%</option>)}</select></label>
  <label>Animation<select value={settings.motion} onChange={event=>update({motion:event.target.value})}><option value="system">Follow device preference</option><option value="reduced">Reduce motion</option></select></label></div>
  <p className="muted">Settings stay on this device and remain active on the connection screen. They do not change approvals, expiry times or permissions. Keyboard and text controls remain available; microphone input is not required.</p>
 </section>
}

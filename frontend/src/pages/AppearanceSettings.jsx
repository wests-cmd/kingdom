import React from 'react'
import {PALETTES} from '../appearance'
import {useAppearance} from '../components/common/AppearanceProvider'
import AccessibilitySettings from '../components/common/AccessibilitySettings'

export default function AppearanceSettings() {
  const {settings,update,saved,reset}=useAppearance()
  return <div className="page-stack appearance-settings">
    <div className="page-heading"><div><p className="eyebrow">Make it yours</p><h1>Settings</h1><p>Shape the look of your Kingdom. Changes apply immediately and stay on this browser or desktop installation.</p></div><button onClick={reset}>Reset appearance</button></div>
    <p role="status" className="muted">{saved?'Appearance saved on this device.':'Changes are active for this session. This browser could not save them.'}</p>
    <AccessibilitySettings />
    <section className="panel appearance-preview" aria-label="Appearance preview"><div><p className="eyebrow">Kingdom</p><h2>Your command room</h2><p className="muted">A quieter canvas. A color that feels like yours.</p></div><div className="preview-chips"><span className="status-chip">Your chosen accent</span><span className="badge-online">Connected</span></div></section>
    <section className="panel"><div className="section-heading"><h2>Color palette</h2></div><p className="muted">Choose a starting palette, or pick your own accent. Success and warning colors retain their meaning.</p><div className="palette-options">{PALETTES.map(p=><button key={p.id} className={`palette-option ${settings.palette===p.id&&settings.accent===p.accent?'selected':''}`} aria-pressed={settings.palette===p.id&&settings.accent===p.accent} onClick={()=>update({palette:p.id,accent:p.accent})}><span className="palette-swatch" style={{background:p.accent}} aria-hidden="true"/><strong>{p.name}</strong><small>{p.description}</small></button>)}</div><div className="appearance-field"><label htmlFor="appearance-accent">Custom accent color</label><div className="color-control"><input id="appearance-accent" type="color" value={settings.accent} onChange={e=>update({accent:e.target.value})}/><input key={settings.accent} aria-label="Hex accent color" className="accent-hex" defaultValue={settings.accent.toUpperCase()} maxLength={7} spellCheck={false} onBlur={e=>{if(/^#[0-9a-f]{6}$/i.test(e.target.value))update({accent:e.target.value});else e.target.value=settings.accent.toUpperCase()}} onKeyDown={e=>{if(e.key==='Enter')e.target.blur()}}/></div><small>Pick a color or enter a six-digit hex code and press Enter. Text contrast adjusts automatically.</small></div></section>
    <section className="panel"><h2>Display</h2><div className="appearance-fields">
      <label>Color mode<select value={settings.mode} onChange={e=>update({mode:e.target.value})}><option value="dark">Dark</option><option value="light">Light</option><option value="system">Match device</option></select></label>
      <label>Spacing<select value={settings.density} onChange={e=>update({density:e.target.value})}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
      <label>Display size<select value={settings.scale} onChange={e=>update({scale:Number(e.target.value)})}>{[90,100,110,125,150,175,200].map(v=><option key={v} value={v}>{v}%{v===100?' (default)':''}</option>)}</select></label>
      <label>Motion<select value={settings.motion} onChange={e=>update({motion:e.target.value})}><option value="system">Respect device preference</option><option value="reduced">Reduce motion</option></select></label>
      <label>Background atmosphere<select value={settings.atmosphere} onChange={e=>update({atmosphere:Number(e.target.value)})}>{[0,5,10,15,20].map(v=><option key={v} value={v}>{v===0?'Off':v+'%'}</option>)}</select></label>
    </div></section>
    <p className="muted">These controls change appearance only. Runtime autonomy, approvals and access permissions remain under Governance and Security.</p>
  </div>
}

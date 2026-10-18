import React, {useState} from 'react'
import api from '../api'

// Reporting lines are independent of the computer that actually hosts a tool.
export default function CoordinationGraph({graph}) {
 const [draft,setDraft]=useState(null),[saved,setSaved]=useState(null),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[source,setSource]=useState('')
 if(!graph)return null
 const current=saved&&saved.version>graph.version?saved:graph
 const nodes=current.nodes, parents=draft?.parents||current.parents
 const depth=id=>{let level=0,seen=new Set();while(id!=='kingdom'&&parents[id]&&!seen.has(id)){seen.add(id);id=parents[id];level++}return level}
 const move=(id,parent)=>{
  let cursor=parent,seen=new Set([id]);while(cursor!=='kingdom'){if(seen.has(cursor)){setMessage('That line would create a loop. Choose another parent.');return}seen.add(cursor);cursor=parents[cursor]||'kingdom'}
  setDraft({version:draft?.version??current.version,parents:{...parents,[id]:parent}});setMessage('Unsaved coordination changes. Hosting and permissions stay the same.')
 }
 const save=async()=>{setBusy(true);try{const result=await api.put('/hierarchy/topology',draft);setSaved(result.data);setDraft(null);setMessage('Coordination hierarchy saved.')}catch(e){setMessage(e.response?.data?.detail||'Save failed; your draft is retained.')}finally{setBusy(false)}}
 const levels=Array.from({length:Math.max(1,...nodes.map(n=>depth(n.id)))+1},()=>[])
 levels[0]=[{id:'kingdom',label:'Kingdom',kind:'kingdom'}];nodes.forEach(n=>levels[depth(n.id)].push(n))
 const points={};let graphHeight=0;levels.forEach(row=>{row.forEach((n,index)=>{points[n.id]={x:150+(index%2)*300,y:40+graphHeight+Math.floor(index/2)*70}});graphHeight+=Math.max(1,Math.ceil(row.length/2))*70+30})
 return <section className="panel" aria-label="Editable coordination hierarchy" style={{minWidth:0}}>
  <h3>Who coordinates whom</h3><p>Drag a card onto its coordinator, or use the menus. Levels follow the saved reporting lines. Computer hosting, group assignment authority and autonomy levels are separate.</p>
  <svg viewBox={`0 0 600 ${graphHeight}`} role="img" aria-label="Coordination hierarchy. Use the menus below for keyboard editing." style={{width:'100%',minHeight:180,maxHeight:1000}}>
   {nodes.map(n=>{const a=points[n.id],b=points[parents[n.id]];return b&&<line key={n.id} x1={a.x} y1={a.y-18} x2={b.x} y2={b.y+18} stroke="var(--accent-readable)" strokeWidth="2"/>})}
   {Object.entries(points).map(([id,p])=><g key={id}><rect x={p.x-110} y={p.y-18} width="220" height="36" rx="8" fill="var(--surface-dark)" stroke="var(--accent-readable)"/><text x={p.x} y={p.y+4} textAnchor="middle" fill="var(--text-main)" fontSize="18">{id==='kingdom'?'Kingdom':nodes.find(n=>n.id===id)?.label.slice(0,23)}</text></g>)}
  </svg>
  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,240px),1fr))',gap:12}}>
   <div onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(source)move(source,'kingdom');setSource('')}} className="card">Kingdom · drop here for top level</div>
   {nodes.map(n=><div className="card" key={n.id} draggable onDragStart={()=>setSource(n.id)} onDragEnd={()=>setSource('')} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(source)move(source,n.id);setSource('')}} style={{minWidth:0,overflowWrap:'anywhere'}}>
    <strong>{n.kind==='knight'?'🖥':'◇'} {n.label}</strong><p>Level {depth(n.id)} · {n.kind==='knight'?'Computer':'Apprentice'} · Host: {nodes.find(h=>h.id===n.host)?.label||n.host}</p>
    <label>Coordinator for {n.label}<select aria-label={`Coordinator for ${n.label} (${n.id})`} style={{width:'100%',minWidth:0}} value={parents[n.id]} onChange={e=>move(n.id,e.target.value)}><option value="kingdom">Kingdom</option>{nodes.filter(p=>p.id!==n.id).map(p=><option key={p.id} value={p.id}>{p.label} · {p.kind}{p.kind==='apprentice'?` on ${nodes.find(h=>h.id===p.host)?.label||p.host}`:''}</option>)}</select></label>
   </div>)}
  </div>
  <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:12}}><button disabled={!draft||busy} onClick={save}>Save hierarchy</button><button disabled={!draft||busy} onClick={()=>{setDraft(null);setSaved(null);setMessage('Draft discarded; latest reported hierarchy restored.')}}>Discard changes</button></div>
  {message&&<p role="status">{message}</p>}
 </section>
}

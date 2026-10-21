import React, {useState} from 'react'
import api from '../api'
import {coordinationPage, coordinationDepths, coordinatorOptions} from './common/coordination'

// Reporting lines are independent of the computer that actually hosts a tool.
export default function CoordinationGraph({graph}) {
 const [draft,setDraft]=useState(null),[saved,setSaved]=useState(null),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[source,setSource]=useState('')
 const [page,setPage]=useState(0),[editing,setEditing]=useState(''),[query,setQuery]=useState('')
 if(!graph)return null
 const current=saved&&saved.version>graph.version?saved:graph
 const nodes=current.nodes, parents=draft?.parents||current.parents
 const byId=new Map(nodes.map(n=>[n.id,n])), depths=coordinationDepths(nodes,parents)
 const paged=coordinationPage(nodes,page), visible=paged.nodes
 const label=id=>id==='kingdom'?'Kingdom':byId.get(id)?.label||id
 const move=(id,parent)=>{
  if(busy)return
  if(!byId.has(id)||(parent!=='kingdom'&&!byId.has(parent))){setMessage('The participants changed. Discard changes and reopen the editor.');return}
  let cursor=parent,seen=new Set([id]);while(cursor!=='kingdom'){if(seen.has(cursor)){setMessage('That line would create a loop. Choose another parent.');return}seen.add(cursor);cursor=parents[cursor]||'kingdom'}
  setDraft({version:draft?.version??current.version,parents:{...parents,[id]:parent}});setMessage('Unsaved coordination changes. Hosting and permissions stay the same.')
 }
 const save=async()=>{setBusy(true);try{const result=await api.put('/hierarchy/topology',draft);setSaved(result.data);setDraft(null);setMessage('Coordination hierarchy saved.')}catch(e){setMessage(e.response?.data?.detail||'Save failed; your draft is retained.')}finally{setBusy(false)}}
 const rows=new Map();visible.forEach(n=>{const d=depths.get(n.id)||0;if(!rows.has(d))rows.set(d,[]);rows.get(d).push(n)})
 const points={kingdom:{x:300,y:40}};let graphHeight=100
 Array.from(rows).sort((a,b)=>a[0]-b[0]).forEach(([,row])=>{row.forEach((n,index)=>{points[n.id]={x:150+(index%2)*300,y:40+graphHeight+Math.floor(index/2)*70}});graphHeight+=Math.max(1,Math.ceil(row.length/2))*70+30})
 const options=coordinatorOptions(nodes,editing,query,parents[editing])
 return <section className="panel" aria-label="Editable coordination hierarchy" style={{minWidth:0}}>
  <h3>Who coordinates whom</h3><p>Drag a card onto its coordinator, or select Change coordinator. Levels follow reporting lines. Computer hosting, group assignment authority and autonomy levels are separate.</p>
  <nav aria-label="Hierarchy pages" style={{display:'flex',flexWrap:'wrap',gap:8,alignItems:'center'}}><button disabled={!paged.page} onClick={()=>setPage(paged.page-1)}>Previous participants</button><span>Page {paged.page+1} of {paged.pages} · {nodes.length} participants</span><button disabled={paged.page+1>=paged.pages} onClick={()=>setPage(paged.page+1)}>Next participants</button></nav>
  <p className="muted">Up to 20 participants appear per page. Lines connect participants on this page; each card names its coordinator even when it is on another page. Scroll the diagram sideways on narrow screens.</p>
  <div style={{overflowX:'auto',maxWidth:'100%'}} tabIndex="0" aria-label="Scrollable coordination diagram">
   <svg viewBox={`0 0 600 ${graphHeight}`} role="img" aria-label="Coordination hierarchy for this page. Use Change coordinator below for keyboard editing." style={{display:'block',width:'100%',minWidth:600,height:'auto'}}>
    {visible.map(n=>{const a=points[n.id],b=points[parents[n.id]];return b&&<line key={n.id} x1={a.x} y1={a.y-18} x2={b.x} y2={b.y+18} stroke="var(--accent-readable)" strokeWidth="2"/>})}
    {Object.entries(points).map(([id,p])=><g key={id}><title>{label(id)} · Level {depths.get(id)||0}</title><rect x={p.x-110} y={p.y-18} width="220" height="36" rx="8" fill="var(--surface-dark)" stroke="var(--accent-readable)"/><text x={p.x} y={p.y+4} textAnchor="middle" fill="var(--text-main)" fontSize="18">{label(id).slice(0,23)}</text></g>)}
   </svg>
  </div>
  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,240px),1fr))',gap:12}}>
   <div onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(source)move(source,'kingdom');setSource('')}} className="card">Kingdom · drop here for top level</div>
   {visible.map(n=><div className="card" key={n.id} draggable onDragStart={()=>setSource(n.id)} onDragEnd={()=>setSource('')} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(source)move(source,n.id);setSource('')}} style={{minWidth:0,overflowWrap:'anywhere'}}>
    <strong>{n.kind==='knight'?'🖥':'◇'} {n.label}</strong><p>Level {depths.get(n.id)||0} · {n.kind==='knight'?'Computer':'Apprentice'} · Host: {label(n.host)}</p>
    <p>Coordinator: {label(parents[n.id])}</p><button aria-label={`Change coordinator for ${n.label} (${n.id})`} onClick={()=>{setEditing(n.id);setQuery('')}}>Change coordinator</button>
   </div>)}
  </div>
  {byId.has(editing)&&<fieldset style={{minWidth:0,marginTop:12}}><legend>Coordinator for {label(editing)}</legend>
   <label>Find a coordinator<input aria-label="Find a coordinator" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Name or identity" style={{width:'100%'}}/></label>
   <label>Choose coordinator<select disabled={busy} aria-label={`Coordinator for ${label(editing)} (${editing})`} style={{width:'100%',minWidth:0}} value={parents[editing]} onChange={e=>move(editing,e.target.value)}><option value="kingdom">Kingdom</option>{options.nodes.map(n=><option key={n.id} value={n.id}>{n.label} · {n.kind}{n.kind==='apprentice'?` on ${label(n.host)}`:''}</option>)}</select></label>
   {options.total>50&&<p>Showing the first 50 matches and the current coordinator. Search to find another participant.</p>}<button onClick={()=>setEditing('')}>Close coordinator editor</button>
  </fieldset>}
  <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:12}}><button disabled={!draft||busy} onClick={save}>Save hierarchy</button><button disabled={!draft||busy} onClick={()=>{setDraft(null);setSaved(null);setMessage('Draft discarded; latest reported hierarchy restored.')}}>Discard changes</button></div>
  {message&&<p role="status">{message}</p>}
 </section>
}

import React,{useEffect,useMemo,useRef,useState} from 'react'
import api from '../api'
import CoordinationGraph from './CoordinationGraph'
import {jobStatus,serviceStatus} from './common/fleetVisibility'
import {CARD_W,CARD_H,clamp,connectionState,mapNodes,pageNodes,geometry,history,commit,undo,redo,moveCard,moveFrame,resizeFrame,metrics,knightKey} from './common/commandMap'
import './CommandMap.css'

const VIEWS=[['network','Network'],['teams','Team organizer'],['work','Live work']]
const trim=(value,n=26)=>String(value??'Not reported').length>n?String(value).slice(0,n-1)+'…':String(value??'Not reported')
const statusText={local:'Local controller',current:'Current signed report',problem:'Disconnected / restricted',unknown:'Report unavailable'}
const statusColor={local:'#7299c9',current:'#7299c9',problem:'#d96a73',unknown:'#858b97'}
const report=c=>c.activity?.state==='observed'&&Array.isArray(c.activity.jobs)?c.activity.jobs:null

export default function KnightNetworkGraph(props){
 const [view,setView]=useState('network')
 const [dirty,setDirty]=useState(false)
 function choose(next){if(next!==view&&(!dirty||window.confirm('Discard unsaved visual changes?'))){setDirty(false);setView(next)}}
 return <section className="command-map" aria-label="Kingdom Command Center">
  <header><div><h3>Kingdom Command Center</h3><p>One workspace for computers, teams and reported work. Layout edits never change authority.</p></div></header>
  <nav className="command-map-toolbar" aria-label="Map views">{VIEWS.map(([id,label])=><button type="button" key={id} aria-pressed={view===id} onClick={()=>choose(id)}>{label}</button>)}</nav>
  <Canvas key={view} {...props} view={view} onDirty={setDirty}/>
 </section>
}

function Canvas({computers,groups,hierarchy,busy,readOnly,onIntent,onMenu,view,onDirty}){
 const svg=useRef(null),drag=useRef(null),generation=useRef(0)
 const [stored,setStored]=useState(null),[hist,setHist]=useState(history()),[preview,setPreview]=useState(null),[editing,setEditing]=useState(false),[saving,setSaving]=useState(false)
 const [query,setQuery]=useState(''),[page,setPage]=useState(0),[zoom,setZoom]=useState(1),[selected,setSelected]=useState(''),[target,setTarget]=useState(''),[message,setMessage]=useState(''),[conflict,setConflict]=useState(false)
 const dirty=Boolean(stored&&JSON.stringify(hist.doc)!==JSON.stringify(stored.positions))
 const locked=busy||saving
 const path='/hierarchy/map-layout/'+view
 async function load(){
  const serial=++generation.current
  try{const {data}=await api.get(path);if(serial!==generation.current)return;setStored(data);setHist(history(data.positions));setPreview(null);setConflict(false);setMessage('');setEditing(false)}
  catch{if(serial===generation.current)setMessage('Layout unavailable. Current organization is still visible; reload before editing.')}
 }
 useEffect(()=>{void load();return()=>{generation.current++}},[path])
 useEffect(()=>{onDirty(dirty);if(!dirty)return;const warn=e=>{e.preventDefault();e.returnValue=''};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[dirty,onDirty])
 const all=useMemo(()=>mapNodes(computers,groups,hierarchy?.topology,view),[computers,groups,hierarchy?.topology,view])
 const paging=pageNodes(all,query,page),nodes=paging.nodes
 const model=geometry(nodes,groups,preview||hist.doc)
 const node=nodes.find(n=>n.key===selected),frame=model.frames.find(f=>f.key===selected)
 const chosen=node?.computer,team=groups.find(g=>g.id===(node?.group||frame?.id))
 const pos=node&&model.boxes[node.key]
 const byId=new Map(nodes.map(n=>[n.id,n]))
 const local=model.boxes[knightKey('local')]
 const select=key=>{setSelected(key);setTarget('')}
 function apply(doc){setHist(old=>commit(old,doc));setPreview(null)}
 function pointer(e){
  const p=svg.current.createSVGPoint();p.x=e.clientX;p.y=e.clientY
  return p.matrixTransform(svg.current.getScreenCTM().inverse())
 }
 function start(e,item,isFrame=false){
  if(e.button!==0||locked)return
  e.stopPropagation();select(item.key)
  if(!editing||conflict)return
  e.preventDefault();const p=pointer(e)
  drag.current={id:e.pointerId,key:item.key,frame:isFrame?item:null,start:p,origin:model.boxes[item.key],boxes:model.boxes,doc:hist.doc,next:null}
  svg.current.setPointerCapture(e.pointerId)
 }
 function move(e){
  const d=drag.current;if(!d||d.id!==e.pointerId)return
  const p=pointer(e),dx=p.x-d.start.x,dy=p.y-d.start.y
  if(Math.hypot(dx,dy)<3&&!d.next)return
  d.next=d.frame?moveFrame(d.doc,d.frame,d.boxes,dx,dy):moveCard(d.doc,d.key,{x:d.origin.x+dx,y:d.origin.y+dy})
  setPreview(d.next)
 }
 function end(e,abort=false){
  const d=drag.current;if(!d||d.id!==e.pointerId)return
  drag.current=null;setPreview(null)
  if(svg.current.hasPointerCapture(e.pointerId))svg.current.releasePointerCapture(e.pointerId)
  if(!abort&&d.next)apply(d.next)
 }
 async function save(){
  if(!stored||!dirty||conflict||locked)return
  setSaving(true);setMessage('')
  try{const {data}=await api.put(path,{version:stored.version,positions:hist.doc});setStored(data);setHist(history(data.positions));setEditing(false);setMessage('Visual layout saved. Membership and permissions are unchanged.')}
  catch(e){if(e.response?.status===409)setConflict(true);setMessage(e.response?.data?.detail||'Could not save layout. Your draft is retained.')}
  finally{setSaving(false)}
 }
 function reload(){if(!dirty||window.confirm('Discard this visual draft and reload the saved layout?'))void load()}
 const keySelect=(e,key)=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(key)}}
 function actionMenu(e,entity){onMenu(e,entity)}
 const jobs=chosen&&report(chosen)
 const grantList=chosen?.grants
 return <>
  <div className="command-map-toolbar" aria-label="Map tools">
   <button type="button" disabled={!stored||locked||conflict} aria-pressed={editing} onClick={()=>setEditing(v=>!v)}>{editing?'Preview layout':'Edit layout'}</button>
   <button type="button" disabled={!editing||!hist.past.length||locked||conflict} onClick={()=>setHist(undo)}>Undo</button>
   <button type="button" disabled={!editing||!hist.future.length||locked||conflict} onClick={()=>setHist(redo)}>Redo</button>
   <button type="button" disabled={!dirty||locked||conflict} onClick={save}>Save layout</button>
   <button type="button" disabled={locked} onClick={reload}>Reload layout</button>
   <button type="button" disabled={!editing||locked||conflict} onClick={()=>apply({})}>Auto arrange</button>
   <button type="button" aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(.25,z-.15))}>−</button>
   <button type="button" onClick={()=>setZoom(Math.min(1,900/model.width))}>Fit</button>
   <button type="button" aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(2,z+.15))}>+</button>
   <span>{dirty?'Unsaved layout':stored?'Saved layout v'+stored.version:'Default layout'}</span>
  </div>
  {message&&<p role="status" className="command-map-notice">{message}</p>}
  <div className="command-map-toolbar"><label>Find participant <input value={query} onChange={e=>{setQuery(e.target.value);setPage(0);select('')}} placeholder="Name or identity"/></label><button type="button" disabled={paging.page===0} onClick={()=>{setPage(paging.page-1);select('')}}>Previous</button><span>{paging.page+1}/{paging.pages} · {paging.total} participants</span><button type="button" disabled={paging.page+1>=paging.pages} onClick={()=>{setPage(paging.page+1);select('')}}>Next</button></div>
  <p className="command-map-note">{editing?'Drag cards or frame headers to arrange the current page. Use the inspector for keyboard positioning and frame size.':'Select a card or team frame for details and actions.'} Team changes use separate reviewed actions. Only 40 participants are rendered per page; lines and frames reflect the visible page.</p>
  <div className="command-map-grid">
   <div className="command-map-scroll" tabIndex={0} aria-label="Scrollable command map">
    <svg ref={svg} width={model.width*zoom} height={model.height*zoom} viewBox={`0 0 ${model.width} ${model.height}`} role="group" aria-label="Interactive Kingdom workspace" onPointerMove={move} onPointerUp={e=>end(e)} onPointerCancel={e=>end(e,true)} onContextMenu={e=>actionMenu(e,null)}>
     <defs><pattern id="command-map-grid" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="8" cy="8" r=".7" fill="#343945"/></pattern></defs>
     <rect width={model.width} height={model.height} fill="url(#command-map-grid)"/>
     {model.frames.map(f=><g key={f.key} role="button" tabIndex={0} aria-label={f.label+' team frame'} onPointerDown={e=>start(e,f,true)} onKeyDown={e=>keySelect(e,f.key)} onContextMenu={e=>actionMenu(e,groups.find(g=>g.id===f.id)||null)}>
      <rect x={f.x} y={f.y} width={f.w} height={f.h} rx="8" fill="#191d25" fillOpacity=".65" stroke={selected===f.key?'#8ab1e2':'#555e6d'} strokeDasharray="5 4"/>
      <text x={f.x+12} y={f.y+23} className="command-frame-label">{trim(f.label,38)} · {f.members.length} visible</text>
     </g>)}
     {view==='network'&&local&&nodes.filter(n=>n.kind==='knight'&&n.id!=='local').map(n=>{const a=local,b=model.boxes[n.key],state=connectionState(n.computer);return <path key={n.key} d={`M ${a.x+CARD_W/2} ${a.y+CARD_H} L ${b.x+CARD_W/2} ${b.y}`} stroke={statusColor[state]} strokeWidth="2" strokeDasharray={state==='current'?undefined:'6 5'} fill="none" pointerEvents="none"/>})}
     {view==='teams'&&nodes.map(n=>{const parent=byId.get(hierarchy?.topology?.parents?.[n.id]);if(!parent)return null;const a=model.boxes[parent.key],b=model.boxes[n.key];return <path key={n.key} d={`M ${a.x+CARD_W/2} ${a.y+CARD_H} L ${b.x+CARD_W/2} ${b.y}`} stroke="#7299c9" strokeWidth="2" strokeDasharray="4 3" fill="none" pointerEvents="none"/>})}
     {nodes.map(n=>{const p=model.boxes[n.key],c=n.computer,state=connectionState(c),g=groups.find(g=>g.id===n.group),cpu=metrics(c.load?.cpu_percent),ram=metrics(c.load?.memory_percent),work=report(c);return <g key={n.key} transform={`translate(${p.x},${p.y})`} role="button" tabIndex={0} className="command-node" aria-label={n.label+', '+(n.kind==='apprentice'?'Apprentice':statusText[state])} onPointerDown={e=>start(e,n)} onKeyDown={e=>keySelect(e,n.key)} onContextMenu={e=>{if(n.kind==='knight')actionMenu(e,c);else{e.preventDefault();e.stopPropagation();select(n.key)}}}>
      <title>{n.label} · {n.kind==='apprentice'?'Hosted on '+c.name:statusText[state]}</title>
      <rect width={CARD_W} height={CARD_H} rx="7" fill="#222630" stroke={selected===n.key?'#c4ddff':statusColor[state]} strokeWidth={selected===n.key?2.5:1.4}/>
      {n.kind==='knight'?<><rect x="12" y="12" width="30" height="20" rx="2" fill="none" stroke="#b9c2d0" strokeWidth="1.5"/><path d="M 27 32 v5 M 17 38 h20" stroke="#b9c2d0" strokeWidth="1.5"/></>:<><rect x="14" y="12" width="26" height="24" rx="5" fill="none" stroke="#b9c2d0"/><circle cx="22" cy="22" r="2" fill="#b9c2d0"/><circle cx="32" cy="22" r="2" fill="#b9c2d0"/></>}
      <text x="50" y="20" className="command-card-title">{trim(n.label,22)}</text>
      <text x="50" y="34" className="command-card-detail">{n.kind==='apprentice'?'Knight Apprentice':g?.captain===c.id?'Team Captain':c.id==='local'?'Controller Knight':'Knight'}</text>
      <circle cx="16" cy="51" r="4" fill={statusColor[state]}/><text x="27" y="55" className="command-card-detail">{trim(n.kind==='apprentice'?'Host: '+c.name:statusText[state],29)}</text>
      <text x="12" y="73" className="command-card-detail">{n.kind==='apprentice'?'Reports to: '+trim(byId.get(hierarchy?.topology?.parents?.[n.id])?.label||hierarchy?.topology?.parents?.[n.id]||'Unknown',21):view==='work'?(work?work.length+' reported work records':'Work not reported'):`CPU ${cpu===null?'—':cpu+'%'} · RAM ${ram===null?'—':ram+'%'}`}</text>
      <text x="12" y="92" className="command-card-detail">{n.kind==='apprentice'?'Hosting is separate from reporting':work?.length?trim(jobStatus(work[0].status)+' · '+work[0].kind,33):'Select to inspect'}</text>
     </g>})}
    </svg>
   </div>
   <aside className="command-map-inspector" aria-label="Map inspector">
    <h4>{node?.label||frame?.label||'Inspector'}</h4>
    {!node&&!frame&&<p>Select a computer, Apprentice or team frame. Blue indicates a current signed report or the local controller, red indicates a reported problem, gray indicates unknown. Network lines are peer report relationships, not physical wiring or proven transport paths.</p>}
    {node&&<><p>{node.kind==='apprentice'?'Hosted on '+chosen.name:statusText[connectionState(chosen)]}</p><p>Team: {team?.name||'Unassigned'}</p>
     {node.kind==='knight'&&<><p>Leader: {team?.captain===node.id?'This Knight':team?.captain||'Unassigned'}</p><button type="button" disabled={locked} onClick={e=>actionMenu(e,chosen)}>Knight actions</button>
      <label>Move to team<select value={target} disabled={readOnly||locked} onChange={e=>setTarget(e.target.value)}><option value="">Choose team</option>{groups.filter(g=>g.id!==node.group).map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label><button type="button" disabled={!target||readOnly||locked} onClick={()=>onIntent({kind:'add',group:target,members:[node.id]})}>Review team move</button>
      {team&&<button type="button" disabled={readOnly||locked} onClick={()=>onIntent({kind:'remove',members:[node.id]})}>Review removal</button>}
     </>}
     {node.kind==='apprentice'&&<p>Coordinator: {byId.get(hierarchy?.topology?.parents?.[node.id])?.label||hierarchy?.topology?.parents?.[node.id]||'Unknown'}. Edit reporting below; this does not relocate the agent.</p>}
     {editing&&pos&&<fieldset disabled={locked||conflict}><legend>Move visually</legend>{['x','y'].map(k=><label key={k}>{k.toUpperCase()}<input type="number" min="0" max="100000" step="16" value={pos[k]} onChange={e=>apply(moveCard(hist.doc,node.key,{...pos,[k]:clamp(Number(e.target.value))}))}/></label>)}</fieldset>}
     <h4>Reported work</h4>{jobs?<ul>{jobs.slice(0,8).map(j=><li key={j.kind+'/'+j.id}>{jobStatus(j.status)} · {j.kind}{j.tool?' · '+j.tool:''}{j.model?' · '+j.model:''}{j.worker?' · '+j.worker:''}</li>)}</ul>:<p>Unavailable, not zero work.</p>}{jobs?.length===0&&<p>No retained work records.</p>}
     <h4>Services</h4>{chosen.services?.state==='observed'?<ul>{(chosen.services.services||[]).slice(0,8).map(s=><li key={s.id}>{s.name} · {serviceStatus(s)}</li>)}</ul>:<p>Not reported.</p>}
     <h4>Reported grants</h4>{Array.isArray(grantList)?<p>{grantList.join(', ')||'None reported'}</p>:<p>Not reported here. Inspect permissions separately.</p>}
    </>}
    {frame&&<><p>{frame.members.length} participants on this page; saved team membership is independent of the frame.</p>{team&&<button type="button" disabled={locked} onClick={e=>actionMenu(e,team)}>Team actions</button>}
     {editing&&<fieldset disabled={locked||conflict}><legend>Frame minimum size</legend>{['w','h'].map(k=><label key={k}>{k==='w'?'Width':'Height'}<input type="number" min="32" max="20000" step="16" value={frame[k]} onChange={e=>apply(resizeFrame(hist.doc,frame,k==='w'?Number(e.target.value):frame.w,k==='h'?Number(e.target.value):frame.h))}/></label>)}<p>Frame always encloses visible members.</p></fieldset>}</>}
   </aside>
  </div>
  <p className="command-map-note">Work and resource reports are not independent verification. Visual changes are local to this controller; shared team membership still uses its authority controller.</p>
  {view==='teams'&&<details><summary>Edit reporting relationships</summary><CoordinationGraph graph={hierarchy?.topology}/></details>}
 </>
}

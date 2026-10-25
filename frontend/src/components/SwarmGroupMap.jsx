import React,{useEffect,useRef,useState} from 'react'
import api from '../api'
import {memberChoices,splitSizes} from './common/swarmGroups'
import {computerName} from './common/computerName'
import {apprenticeLabel} from './common/presentation'
import {jobStatus,serviceStatus} from './common/fleetVisibility'
import './SwarmGroupMap.css'

function Modal({title,busy,onClose,children}) {
 const ref=useRef(null)
 useEffect(()=>{const previous=document.activeElement;ref.current.showModal();return()=>previous?.focus?.()},[])
 return <dialog ref={ref} className="swarm-dialog" onCancel={e=>{e.preventDefault();if(!busy)onClose()}} aria-label={title}>
  <header><h3>{title}</h3><button type="button" disabled={busy} aria-label="Close dialog" onClick={onClose}>Close</button></header>{children}
 </dialog>
}
const labels=value=>value.split(',').map(v=>v.trim()).filter(Boolean)

export default function SwarmGroupMap({computers,hierarchy,onRefresh}) {
 const [snapshot,setSnapshot]=useState(null),[menu,setMenu]=useState(null),[draft,setDraft]=useState(null)
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(null)
 const [timeout,setTimeoutHours]=useState(hierarchy.visibility?.offline_hours||168)
 useEffect(()=>{setSnapshot(null);setTimeoutHours(hierarchy.visibility?.offline_hours||168)},[hierarchy])
 useEffect(()=>{if(!menu)return;const close=e=>{if(!e.target.closest('.swarm-context'))setMenu(null)};const key=e=>{if(e.key==='Escape')setMenu(null)};document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key)}},[menu])
 const groups=snapshot?.groups||hierarchy.groups||[],version=snapshot?.version||hierarchy.groups_version
 const all=[...computers,...(hierarchy.archived_knights||[]).filter(n=>['APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'].includes(n.node_state)).map(n=>({id:n.node_id||n.id,name:computerName(n.display_username,n.display_computer||n.hostname,n.node_id||n.id),state:'Archived · offline',archived:true}))]
 const title=id=>all.find(c=>c.id===id)?.name||`Unavailable Knight ${id.slice(-8)}`
 const close=()=>{setDraft(null);setConfirm(null)}
 const edit=(group=null,people=[])=>{if(hierarchy.groups_read_only){setMessage(hierarchy.groups_notice);setMenu(null);return}setMenu(null);setMessage('');setDraft({kind:'save',version,group_ids:group?[group.id]:[],name:group?.name||'',members:group?[...group.members]:people,captain:group?.captain||people[0]||'',flags:(group?.flags||[]).join(', '),preferred:(group?.preferred_task_types||[]).join(', '),move:false})}
 const mutate=async body=>{
  if(hierarchy.groups_read_only){setMessage(hierarchy.groups_notice);return}
  setBusy(true);setMessage('')
  try {const {data}=await api.post('/hierarchy/groups/edit',body);setSnapshot(data);close();setMenu(null);setMessage('Groups saved. Permissions are unchanged.');await onRefresh?.()}
  catch(e){setMessage(e.response?.data?.detail||'Could not save groups. Refresh and try again.')}
  finally{setBusy(false)}
 }
 const save=()=>{
  const conflicts=groups.filter(g=>!draft.group_ids.includes(g.id)&&g.members.some(id=>draft.members.includes(id)))
  const body={version:draft.version,operation:'save',group_ids:draft.group_ids,name:draft.name,captain:draft.captain,members:draft.members,flags:labels(draft.flags),preferred_task_types:labels(draft.preferred),move:draft.move}
  if(conflicts.length&&!draft.move){setConfirm({text:`Move the selected Knights out of ${conflicts.map(g=>g.name).join(', ')} and into ${draft.name}? Empty source groups will be removed.`,run:()=>mutate({...body,move:true})});return}
  mutate(body)
 }
 const toggle=c=>{
  const apply=()=>{setDraft(old=>{const members=old.members.includes(c.id)?old.members.filter(id=>id!==c.id):[...old.members,c.id];return {...old,members,captain:members.includes(old.captain)?old.captain:members[0]||'',move:old.move||!!c.other}});setConfirm(null)}
  if(c.other&&!draft.members.includes(c.id)){setConfirm({text:`Take ${c.name} out of ${c.other.name} and put it in this group when you save?`,run:apply});return}
  apply()
 }
 const openMenu=(event,target)=>{event.preventDefault();event.stopPropagation();setMenu({target,x:Math.max(8,Math.min(event.clientX,window.innerWidth-245)),y:Math.max(8,Math.min(event.clientY,window.innerHeight-330))})}
 const drop=(event,target)=>{
  event.preventDefault();event.stopPropagation();if(busy||hierarchy.groups_read_only)return
  const id=event.dataTransfer.getData('text/plain');if(!computers.some(c=>c.id===id))return
  if(target?.members){edit(target);setDraft(old=>({...old,members:[...new Set([...target.members,id])]}))}
  else if(target?.id&&target.id!==id)edit(null,[target.id,id])
  else if(!target&&groups.some(g=>g.members.includes(id)))setConfirm({text:`Remove ${title(id)} from its group?`,run:()=>mutate({version,operation:'unassign',members:[id]})})
 }
 const node=computer=><button type="button" key={computer.id} className={`swarm-knight ${computer.current||computer.id==='local'?'':'disconnected'}`} draggable={!busy&&!hierarchy.groups_read_only}
  onDragStart={e=>e.dataTransfer.setData('text/plain',computer.id)} onDragOver={e=>e.preventDefault()} onDrop={e=>drop(e,computer)}
  onContextMenu={e=>openMenu(e,computer)} onClick={e=>openMenu(e,computer)} disabled={busy} aria-label={`${computer.name}: ${computer.state}. Open Knight actions`}>
  <strong>{computer.name}</strong><span>{computer.state}</span><span className="muted">Actions ⋯</span>
 </button>
 const grouped=new Set(groups.flatMap(g=>g.members))
 const context=menu?.target,team=context?.members?context:null
 return <section className="swarm-group-map" aria-label="Interactive Kingdom diagram">
  {hierarchy.groups_notice&&<p role={hierarchy.groups_read_only?'status':undefined}>{hierarchy.groups_notice}</p>}
  <div className="action-row"><button type="button" disabled={busy||!version} onClick={()=>edit()}>Make group</button><button type="button" onClick={()=>{setMenu(null);setDraft({kind:'visibility'})}}>Offline list timeout</button><button type="button" onClick={()=>onRefresh?.()}>Refresh map</button></div>
  <p>Drag a Knight onto another to make a group, into a group to add it, or onto Ungrouped to remove it. Right-click or select any card for actions. Disconnected Knights keep their place until the offline-list timeout.</p>
  <div className="swarm-fit-map" onContextMenu={e=>openMenu(e,null)}>
   {groups.map(g=><section key={g.id} className="swarm-team" onContextMenu={e=>openMenu(e,g)} onDragOver={e=>e.preventDefault()} onDrop={e=>drop(e,g)}>
    <header><h3>{g.name}</h3><button type="button" disabled={busy} onClick={e=>openMenu(e,g)} aria-label={`${g.name} group actions`}>⋯</button></header>
    <p>Leader: {title(g.captain)}</p><div className="swarm-card-grid">{computers.filter(c=>g.members.includes(c.id)).map(node)}</div>
    {!!g.members.filter(id=>!computers.some(c=>c.id===id)).length&&<p className="muted">{g.members.filter(id=>!computers.some(c=>c.id===id)).length} archived or unavailable members. Edit group to inspect membership.</p>}
    {!!g.flags?.length&&<p>Flags: {g.flags.join(', ')}</p>}{!!g.preferred_task_types?.length&&<p>Preferred work: {g.preferred_task_types.join(', ')}</p>}
   </section>)}
   <section className="swarm-team ungrouped" onDragOver={e=>e.preventDefault()} onDrop={e=>drop(e,null)}><h3>Ungrouped Knights</h3><div className="swarm-card-grid">{computers.filter(c=>!grouped.has(c.id)).map(node)}</div>{computers.every(c=>grouped.has(c.id))&&<p>Drop a Knight here to remove it from a group.</p>}</section>
  </div>
  {menu&&<div className="swarm-context card" role="menu" aria-label="Swarm actions" style={{left:menu.x,top:menu.y}}>
   <strong>{team?.name||context?.name||'Kingdom'}</strong>
   <button role="menuitem" onClick={()=>edit()}>Make group</button>
   {team?<><button role="menuitem" onClick={()=>edit(team)}>Edit members, name, leader or flags</button><button role="menuitem" disabled={groups.length<2} onClick={()=>{setDraft({kind:'combine',version,group_ids:[team.id],name:team.name});setMenu(null)}}>Combine groups</button><button role="menuitem" disabled={team.members.length<2} onClick={()=>{setDraft({kind:'split',version,group_ids:[team.id],source:team,count:2,names:[`${team.name} 1`,`${team.name} 2`]});setMenu(null)}}>Split group</button><button role="menuitem" onClick={()=>{setMenu(null);setConfirm({text:`Dissolve ${team.name}? Its Knights remain in this Kingdom.`,run:()=>mutate({version,operation:'remove',group_ids:[team.id]})})}}>Dissolve group</button></>:context?<><button role="menuitem" onClick={()=>{setMenu(null);setDraft({kind:'inspect',computer:context})}}>View work, Apprentices and services</button><button role="menuitem" onClick={()=>edit(null,[context.id])}>Make group with this Knight</button>{groups.map(g=><button key={g.id} role="menuitem" onClick={()=>{if(hierarchy.groups_read_only)return;edit(g);setDraft(old=>({...old,members:[...new Set([...g.members,context.id])]}))}}>Add to {g.name}</button>)}{grouped.has(context.id)&&<button role="menuitem" onClick={()=>{setMenu(null);setConfirm({text:`Remove ${context.name} from its group?`,run:()=>mutate({version,operation:'unassign',members:[context.id]})})}}>Remove from group</button>}</>:null}
   <button role="menuitem" onClick={()=>{setMenu(null);setDraft({kind:'visibility'})}}>Offline list timeout</button><button role="menuitem" onClick={()=>setMenu(null)}>Close menu</button>
  </div>}
  {draft&&<Modal title={({save:'Group settings',combine:'Combine groups',split:'Split group',inspect:draft.computer?.name,visibility:'Offline list timeout'})[draft.kind]} busy={busy} onClose={close}>
   {draft.kind==='save'&&<form onSubmit={e=>{e.preventDefault();save()}}><label>Group name<input autoFocus required maxLength={100} value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>
    <fieldset disabled={busy}><legend>Choose Knights · {draft.members.length} selected</legend><p>Knights in another group appear last in gray. Selecting one asks before moving it.</p>
     <div className="action-row"><button type="button" onClick={()=>setDraft({...draft,members:all.map(c=>c.id),captain:draft.captain||all[0]?.id||'',move:false})}>Select all Knights</button><button type="button" onClick={()=>setDraft({...draft,members:[],captain:''})}>Clear selection</button></div>
     {memberChoices(all,groups,draft.group_ids[0],draft.members).map(c=><label key={c.id} className={c.other?'other-team':''}><input type="checkbox" checked={c.checked} onChange={()=>toggle(c)}/>{c.name}{c.other&&` · in ${c.other.name}`}{c.archived&&' · archived'}</label>)}
    </fieldset><label>Team leader<select required value={draft.captain} onChange={e=>setDraft({...draft,captain:e.target.value})}><option value="">Choose a member</option>{draft.members.map(id=><option key={id} value={id}>{title(id)}</option>)}</select></label>
    <label>Flags, separated by commas<input maxLength={960} value={draft.flags} onChange={e=>setDraft({...draft,flags:e.target.value})}/></label><label>Preferred task types, separated by commas<input maxLength={960} value={draft.preferred} onChange={e=>setDraft({...draft,preferred:e.target.value})}/></label>
    <p>Groups organize work. Permissions and approvals are enforced separately.</p><button disabled={busy||!draft.members.length}>Save group</button></form>}
   {draft.kind==='combine'&&<form onSubmit={e=>{e.preventDefault();mutate({version:draft.version,operation:'combine',group_ids:draft.group_ids,name:draft.name})}}><label>Combined group name<input autoFocus required maxLength={100} value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label><fieldset disabled={busy}><legend>Choose groups to combine</legend>{groups.map(g=><label key={g.id}><input type="checkbox" checked={draft.group_ids.includes(g.id)} onChange={e=>setDraft({...draft,group_ids:e.target.checked?[...draft.group_ids,g.id]:draft.group_ids.filter(id=>id!==g.id)})}/>{g.name} · {g.members.length} Knights</label>)}</fieldset><p>The first selected team's leader is retained. Members and preference labels are combined.</p><button disabled={busy||draft.group_ids.length<2}>Combine selected groups</button></form>}
   {draft.kind==='split'&&<form onSubmit={e=>{e.preventDefault();mutate({version:draft.version,operation:'split',group_ids:draft.group_ids,names:draft.names})}}><label>Number of groups<input autoFocus type="number" min="2" max={draft.source.members.length} required value={draft.count} onChange={e=>{const count=Number(e.target.value);if(count>=2&&count<=draft.source.members.length)setDraft({...draft,count,names:Array.from({length:count},(_,i)=>draft.names[i]||`${draft.source.name} ${i+1}`)})}}/></label>{draft.names.map((name,i)=><label key={i}>Group {i+1} · {splitSizes(draft.source.members.length,draft.count)[i]} Knights<input required maxLength={100} value={name} onChange={e=>setDraft({...draft,names:draft.names.map((n,j)=>i===j?e.target.value:n)})}/></label>)}<p>Extra Knights go into the first group, then the next if needed. Each group starts with its first member as leader.</p><button disabled={busy}>Split group</button></form>}
   {draft.kind==='visibility'&&<form onSubmit={async e=>{e.preventDefault();setBusy(true);try{await api.put('/hierarchy/visibility',{offline_hours:Number(timeout)});close();await onRefresh?.();setMessage('Offline list timeout saved. Pairing and permissions are retained.')}catch(e){setMessage(e.response?.data?.detail||'Could not save timeout.')}finally{setBusy(false)}}}><label>Hide Knights after this many hours offline<input autoFocus required type="number" min="12" max="240" step="1" value={timeout} onChange={e=>setTimeoutHours(e.target.value)}/></label><p>Default: 168 hours (7 days). Allowed: 12 hours to 240 hours (10 days). Hidden Knights remain in the archive and reappear when verified online.</p><button disabled={busy}>Save timeout</button></form>}
   {draft.kind==='inspect'&&<><p>{draft.computer.state}</p><h4>Apprentices</h4>{draft.computer.apprentices?.length?<ul>{draft.computer.apprentices.map(a=><li key={a.id}>{apprenticeLabel(a)} · {a.status||'Unknown'}</li>)}</ul>:<p>No fresh Apprentice report.</p>}<h4>Reported work</h4>{draft.computer.activity?.state==='observed'?<ul>{draft.computer.activity.jobs.map(j=><li key={j.id}>{jobStatus(j.status)} · {j.kind} · {j.id.slice(0,8)}</li>)}</ul>:<p>Fresh work information unavailable.</p>}<h4>Running and startup services</h4>{draft.computer.services?.state==='observed'?<ul>{draft.computer.services.services.map(s=><li key={s.id}>{s.name} · {serviceStatus(s)}</li>)}</ul>:<p>Fresh service information unavailable.</p>}</>}
   {message&&<p role="alert">{message}</p>}
  </Modal>}
  {confirm&&<Modal title="Confirm group change" busy={busy} onClose={()=>setConfirm(null)}><p>{confirm.text}</p><button disabled={busy} onClick={confirm.run}>Yes, continue</button><button disabled={busy} onClick={()=>setConfirm(null)}>Cancel</button>{message&&<p role="alert">{message}</p>}</Modal>}
  {message&&!draft&&<p role="status">{message}</p>}
 </section>
}

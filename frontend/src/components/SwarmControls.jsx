import React, {useState} from 'react'
import api from '../api'
import TaskTypePriorities from './TaskTypePriorities'
const labels=value=>value.split(',').map(item=>item.trim()).filter(Boolean)
export default function SwarmControls({hierarchy}) {
 const [name,setName]=useState(''),[members,setMembers]=useState([]),[captain,setCaptain]=useState(''),[flags,setFlags]=useState(''),[preferred,setPreferred]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[groups,setGroups]=useState(null),[drafts,setDrafts]=useState({}),[saved,setSaved]=useState({})
 const nodes=(hierarchy.knights||[]).filter(node=>['APPROVED','CONNECTED'].includes(node.node_state))
 const title=id=>nodes.find(node=>(node.node_id||node.id)===id)?.hostname||id
 const teams=groups||hierarchy.groups||[]
 const action=async work=>{setBusy(true);try{await work()}catch(error){setMessage(error.response?.data?.detail||'Change failed. Reload current state before retrying.')}finally{setBusy(false)}}
 return <section className="panel swarm-controls" aria-label="Swarm teams and access"><h3>Teams and access</h3>
 <p>These controls authorize a paired Knight to execute capabilities for this controller. They do not configure Ethernet, Wi-Fi, a firewall, vault sharing, or access between every pair of computers. Reporting lines never grant permissions.</p>
 <h4>What this controller allows each Knight to do</h4>
 {!nodes.length&&<p>No currently approved paired Knights. Pair and verify a computer in Nodes first.</p>}
 {nodes.map(node=>{const id=node.node_id||node.id,current=saved[id]||node.granted_capabilities||[],draft=drafts[id]||current,available=[...new Set([...(node.capabilities||[]),...current])];return <details className="card" key={id}><summary>{title(id)} · {current.length} granted capabilities</summary><p>Destination: {id}. Current approval, execution policy and operating system permissions remain required.</p>
 {available.length?available.map(cap=><label key={cap} style={{display:'block'}}><input type="checkbox" disabled={busy} checked={draft.includes(cap)} onChange={event=>setDrafts(old=>({...old,[id]:event.target.checked?[...draft,cap]:draft.filter(item=>item!==cap)}))}/>{cap}</label>):<p>No capabilities advertised. Missing capabilities are not silently granted.</p>}
 <button disabled={busy||!drafts[id]} onClick={()=>action(async()=>{await api.post(`/nodes/${encodeURIComponent(id)}/capabilities`,{granted_capabilities:draft});const response=await api.get(`/nodes/${encodeURIComponent(id)}/capabilities`);setSaved(old=>({...old,[id]:response.data.granted_capabilities}));setDrafts(old=>{const next={...old};delete next[id];return next});setMessage('Grants saved and read back. Remote execution has not been tested.')})}>Save reviewed capability grants</button></details>})}
 <h4>Teams and team leaders</h4><p>A leader can assign only within its approved team through existing assignment checks. Teams add no grants. Flags and preferred task types are planning notes: they do not change queue priority or force placement.</p>
 {teams.map(team=><div className="card" key={team.id}><strong>{team.name}</strong><p>Leader: {title(team.captain)} · Members: {team.members.map(title).join(', ')}</p><p>Flags: {(team.flags||[]).join(', ')||'None'} · Preferred types: {(team.preferred_task_types||[]).join(', ')||'None'}</p><button disabled={busy} onClick={()=>action(async()=>{await api.delete(`/hierarchy/groups/${encodeURIComponent(team.id)}`);setGroups(teams.filter(item=>item.id!==team.id));setMessage('Team removed. Computer grants are unchanged.')})}>Remove team</button></div>)}
 <form onSubmit={event=>{event.preventDefault();action(async()=>{const response=await api.post('/hierarchy/groups',{name,captain,members,flags:labels(flags),preferred_task_types:labels(preferred)});setGroups([...teams,response.data]);setName('');setMembers([]);setCaptain('');setFlags('');setPreferred('');setMessage('Team saved. Planning preferences grant no permissions.')})}}>
 <label>Team name<input required maxLength={100} value={name} onChange={event=>setName(event.target.value)}/></label>
 <fieldset disabled={busy}><legend>Approved member Knights</legend>{nodes.map(node=>{const id=node.node_id||node.id;return <label key={id} style={{display:'block'}}><input type="checkbox" checked={members.includes(id)} onChange={event=>{setMembers(old=>event.target.checked?[...old,id]:old.filter(item=>item!==id));if(captain===id&&!event.target.checked)setCaptain('')}}/>{title(id)}</label>})}</fieldset>
 <label>Team leader<select required disabled={busy} value={captain} onChange={event=>setCaptain(event.target.value)}><option value="">Choose a team member</option>{members.map(id=><option key={id} value={id}>{title(id)}</option>)}</select></label>
 <label>Flags, separated by commas<input maxLength={960} value={flags} onChange={event=>setFlags(event.target.value)}/></label>
 <label>Preferred task types, separated by commas<input maxLength={960} value={preferred} onChange={event=>setPreferred(event.target.value)}/></label>
 <button disabled={busy||!members.length||!captain}>Create team</button></form>{message&&<p role="status">{message}</p>}<TaskTypePriorities/></section>
}

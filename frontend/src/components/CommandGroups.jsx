import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
export default function CommandGroups(){
 const {data,error,refresh}=useLiveData('/hierarchy',10000)
 const [name,setName]=useState(''),[captain,setCaptain]=useState(''),[members,setMembers]=useState([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const eligible=(data?.knights||[]).filter(node=>['APPROVED','CONNECTED'].includes(node.node_state))
 const save=async event=>{event.preventDefault();setBusy(true);try{await api.post('/hierarchy/groups',{name,captain,members});setName('');setMembers([]);setCaptain('');await refresh();setMessage('Group created. Its Captain can assign approved work within this group.')}catch(e){setMessage(e.response?.data?.detail||'Group could not be created.')}finally{setBusy(false)}}
 return <section className="panel"><h2>Command structure</h2><p>Knights are computers. Knight Apprentices are agents or bots on those computers. The Commander controls all approved groups; a Knight Captain controls its own group.</p>{error&&<p role="alert">{error}</p>}
 <p>Commander: {data?.commander?.computer||'Loading…'}</p>
 {(data?.groups||[]).map(group=><div className="record-detail" key={group.id}><h3>{group.name}</h3><p>Captain: {group.captain}</p><p>Knights: {group.members.join(', ')}</p></div>)}
 {!eligible.length?<p className="muted">Pair and approve computers to create a group. Agents running locally are listed separately as Apprentices.</p>:<form onSubmit={save}><label>Group name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label><fieldset><legend>Member computers</legend>{eligible.map(node=><label key={node.id}><input type="checkbox" checked={members.includes(node.id)} onChange={e=>{setMembers(old=>e.target.checked?[...old,node.id]:old.filter(id=>id!==node.id));if(!e.target.checked&&captain===node.id)setCaptain('')}}/>{node.public_identity?.display_name||node.id}</label>)}</fieldset><label>Knight Captain<select required value={captain} onChange={e=>setCaptain(e.target.value)}><option value="">Choose a member computer</option>{members.map(id=><option key={id} value={id}>{eligible.find(node=>node.id===id)?.public_identity?.display_name||id}</option>)}</select></label><button disabled={busy||!members.length||!captain}>Create group</button></form>}
 {message&&<p role="status">{message}</p>}</section>
}

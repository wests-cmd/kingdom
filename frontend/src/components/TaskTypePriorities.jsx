import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
export default function TaskTypePriorities(){
 const {data,error,refresh}=useLiveData('/work-backlog/type-priorities',10000)
 const [kind,setKind]=useState(''),[priority,setPriority]=useState(50),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const save=async priorities=>{setBusy(true);try{await api.put('/work-backlog/type-priorities',{priorities,expected_revision:data.revision});await refresh();setMessage('Task-type priorities saved. Dependencies and permissions still apply.')}catch(error){setMessage(error.response?.data?.detail||'Could not save; reload current priorities before retrying.')}finally{setBusy(false)}}
 return <section className="panel"><h4>Prioritize task types</h4><p>For this controller's work list, higher type priority runs first among eligible work, then item priority and creation time. This never skips dependencies, review, leases or permissions. Unlisted types use 0. Set an outcome's task type in Tasks. Running work is not interrupted.</p>
 {error&&<p role="alert">Could not read priorities.</p>}
 {data&&Object.entries(data.priorities).map(([type,value])=><p key={type}>{type}: {value} <button disabled={busy} onClick={()=>{const next={...data.priorities};delete next[type];save(next)}}>Remove {type} priority</button></p>)}
 <form onSubmit={event=>{event.preventDefault();save({...data.priorities,[kind]:Number(priority)})}}><label>Task type<input required pattern="[A-Za-z0-9_-]{1,80}" maxLength={80} value={kind} onChange={event=>setKind(event.target.value)}/></label><label>Selection priority (0–100)<input required type="number" min="0" max="100" value={priority} onChange={event=>setPriority(event.target.value)}/></label><button disabled={!data||busy||!!error}>Save task-type priority</button></form>{message&&<p role="status">{message}</p>}</section>
}

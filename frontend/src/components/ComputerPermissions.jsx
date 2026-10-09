import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

const labels = {'filesystem.read':'Read workspace files','filesystem.write':'Create and edit workspace files','process.execute':'Run approved commands','computer.observe':'Capture this desktop','computer.control':'Send approved input to an exact Windows foreground window'}
export default function ComputerPermissions(){
 const {data,error,refresh}=useLiveData('/workspace/computer-tools',10000)
 const [drafts,setDrafts]=useState({}),[busy,setBusy]=useState(''),[message,setMessage]=useState('')
 const toggle=(role,cap,current)=>setDrafts(old=>{const selected=old[role]||current;return {...old,[role]:selected.includes(cap)?selected.filter(item=>item!==cap):[...selected,cap]}})
 const save=async apprentice=>{setBusy(apprentice.role);setMessage('');try{await api.put(`/workspace/apprentices/${encodeURIComponent(apprentice.role)}/tools`,{capabilities:drafts[apprentice.role]||apprentice.capabilities});await refresh();setMessage(`Permissions saved for ${apprentice.role}.`)}catch(e){setMessage(e.response?.data?.detail||'Permissions could not be saved.')}finally{setBusy('')}}
 return <section className="panel"><h2>Computer control</h2><p>Choose which Knight Apprentices may use tools on this computer. Grants are separate from the autonomy level.</p><p className="muted">{data?.notice}</p>{error&&<p role="alert">{error}</p>}
 {(data?.apprentices||[]).map(apprentice=><fieldset key={apprentice.role} disabled={!!busy}><legend>{apprentice.role} · Knight Apprentice</legend><div className="appearance-fields">{Object.entries(labels).map(([cap,label])=><label key={cap}><input type="checkbox" checked={(drafts[apprentice.role]||apprentice.capabilities).includes(cap)} onChange={()=>toggle(apprentice.role,cap,apprentice.capabilities)}/>{label}</label>)}</div><button onClick={()=>save(apprentice)}>Save permissions</button></fieldset>)}
 {message&&<p role="status">{message}</p>}</section>
}

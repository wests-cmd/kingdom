import React,{useState} from 'react'
import api from '../api'

export default function HarnessQuickConnect({onSaved}){
 const [found,setFound]=useState(null),[chosen,setChosen]=useState(null),[path,setPath]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const action=async fn=>{setBusy(true);setMessage('');try{await fn()}catch(e){setMessage(e.response?.data?.detail||e.message)}finally{setBusy(false)}}
 return <section className="panel"><h2>Connect an AI worker</h2>
 <p>Choose an installed agent, or connect an API model below. Agents keep their own sign-in and permissions.</p>
 <button disabled={busy} onClick={()=>action(async()=>setFound((await api.get('/harnesses/discovery')).data))}>Find Hermes, Claude or Codex on this computer</button>
 {found&&<><p>{found.notice}</p><div className="action-row">{found.presets.map(p=><button key={p.kind} disabled={busy} onClick={()=>{setChosen(p);setPath(p.executable||'');setMessage('')}}>{p.name} · {p.executable?'found':'choose location'}</button>)}</div></>}
 {chosen&&<form onSubmit={e=>{e.preventDefault();action(async()=>{if(/\.(cmd|bat)$/i.test(path))throw Error('This Windows launcher needs an explicit command interpreter. Use the advanced connection form with its documented launcher.');await api.put(`/harnesses/${chosen.kind}`,{name:chosen.name,kind:chosen.kind,argv:[path,...chosen.arguments],environment:{},timeout_seconds:600});onSaved();setMessage('Connection saved. It has not started a model or changed tool permissions.')})}}>
 <label>Installed executable location<input required value={path} onChange={e=>setPath(e.target.value)} placeholder="Absolute path on the Kingdom host"/></label>
 <p><a href={chosen.documentation} target="_blank" rel="noreferrer">Official {chosen.name} setup</a></p><button disabled={busy||!path}>Save {chosen.name} connection</button></form>}
 {message&&<p role="status">{message}</p>}
 </section>
}

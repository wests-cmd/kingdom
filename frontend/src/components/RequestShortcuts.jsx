import React,{useEffect,useState} from 'react'
import api from '../api'

export default function RequestShortcuts({project,onDraft,disabled}) {
 const [catalog,setCatalog]=useState(null),[name,setName]=useState(''),[command,setCommand]=useState('status'),[notice,setNotice]=useState(''),[saving,setSaving]=useState(false)
 const load=async()=>{const {data}=await api.get('/requests/shortcuts',{params:{project_scope:project}});return {project,...data}}
 useEffect(()=>{let active=true;setCatalog(null);setNotice('');load().then(data=>{if(active)setCatalog(data)}).catch(()=>{if(active)setNotice('Could not load shortcuts')});return()=>{active=false}},[project])
 const current=catalog?.project===project?catalog:null
 const save=async event=>{event.preventDefault();setSaving(true);setNotice('');try{await api.put('/requests/shortcuts',{project_scope:project,name,command});setCatalog(await load());setName('')}catch(e){setNotice(e.response?.data?.detail||'Shortcut could not be saved')}finally{setSaving(false)}}
 const remove=async alias=>{setSaving(true);try{await api.delete('/requests/shortcuts/'+encodeURIComponent(alias),{params:{project_scope:project}});setCatalog(await load())}catch{setNotice('Shortcut could not be removed')}finally{setSaving(false)}}
 return <details><summary>Instant commands and personal shortcuts</summary><p className="muted">Fill the message with a command. Review and Send to run it. Only built-in read-only commands are supported; shortcuts never grant new permissions.</p>
 {current&&<><div style={{display:'flex',gap:6,flexWrap:'wrap'}}>{Object.keys(current.commands).map(key=><button type="button" disabled={disabled} key={key} title={current.commands[key]} onClick={()=>onDraft('/'+key)}>/{key}</button>)}</div>
 <form onSubmit={save}><label>New shortcut name<input value={name} maxLength={40} pattern="[a-z][a-z0-9_-]{0,39}" required disabled={disabled||saving} onChange={e=>setName(e.target.value)}/></label><label>Command<select value={command} disabled={disabled||saving} onChange={e=>setCommand(e.target.value)}>{Object.entries(current.commands).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><button type="submit" disabled={disabled||saving}>Save shortcut for this project</button></form>
 {current.shortcuts.map(row=><div key={row.name}><button type="button" disabled={disabled} onClick={()=>onDraft('/'+row.name)}>/{row.name} → /{row.command}</button> <button type="button" disabled={disabled||saving} onClick={()=>remove(row.name)} aria-label={'Remove shortcut '+row.name}>Remove</button></div>)}</>}
 {notice&&<p role="status">{notice}</p>}</details>
}

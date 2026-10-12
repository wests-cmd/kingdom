import React,{useEffect,useState} from 'react'
import api from '../api'
import {setAccessCode} from '../session'

export default function StartupAccess(){
 const [available,setAvailable]=useState(false),[enabled,setEnabled]=useState(false)
 const [current,setCurrent]=useState(''),[next,setNext]=useState(''),[confirm,setConfirm]=useState('')
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 useEffect(()=>{api.post('/auth/local/status').then(({data})=>{setAvailable(true);setEnabled(data.passcode_enabled)}).catch(()=>{})},[])
 if(!available)return null
 async function save(turnOn){
  if(turnOn && (next.length<6 || next!==confirm)){setMessage('Use at least six characters and enter the same passcode twice.');return}
  setBusy(true);setMessage('')
  try{
   const {data}=await api.put('/auth/local/passcode',{enabled:turnOn,current_passcode:current,new_passcode:next})
   setEnabled(data.passcode_enabled);setCurrent('');setNext('');setConfirm('')
   setMessage(turnOn?'Passcode saved. You chose it; Kingdom will ask for it when you open a new session.':'Passcode turned off. Kingdom opens directly to your main panel.')
  }catch(error){setMessage(error.response?.data?.detail||'Could not save the passcode. Try again.')}
  finally{setBusy(false)}
 }
 async function lock(){
  setBusy(true)
  try{await api.post('/auth/local/lock');setAccessCode('');window.location.reload()}
  catch{setMessage('Could not lock Kingdom. Try again.');setBusy(false)}
 }
 return <section className="panel" aria-label="Startup access"><h2>Opening Kingdom</h2>
  <p>Kingdom opens straight to your main panel on this computer. A passcode is optional and off by default. Other devices still need a connection code.</p>
  <p><strong>{enabled?'Passcode is on':'Passcode is off'}</strong></p>
  <form onSubmit={e=>{e.preventDefault();save(true)}}>
   <div className="appearance-fields">
    {enabled&&<label>Current passcode<input type="password" autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)}/></label>}
    <label>{enabled?'New passcode':'Choose your passcode'}<input type="password" autoComplete="new-password" minLength={6} maxLength={128} value={next} onChange={e=>setNext(e.target.value)}/></label>
    <label>Confirm passcode<input type="password" autoComplete="new-password" maxLength={128} value={confirm} onChange={e=>setConfirm(e.target.value)}/></label>
   </div>
   <p className="muted">Choose a passcode you know. Setup assistants do not create one for you. Your operating system account should also be protected.</p>
   <button disabled={busy} type="submit">{enabled?'Change passcode':'Turn on passcode'}</button>
   {enabled&&<><button disabled={busy} type="button" onClick={()=>save(false)}>Turn off passcode</button><button disabled={busy} type="button" onClick={lock}>Lock now</button></>}
  </form>{message&&<p role="status">{message}</p>}
 </section>
}

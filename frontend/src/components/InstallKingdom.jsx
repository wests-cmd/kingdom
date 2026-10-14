import React, {useEffect,useState} from 'react'

export default function InstallKingdom(){
 const [prompt,setPrompt]=useState(null),[message,setMessage]=useState('')
 useEffect(()=>{
  const ready=event=>{event.preventDefault();setPrompt(event)}
  const installed=()=>{setPrompt(null);setMessage('Kingdom web app installed.')}
  window.addEventListener('beforeinstallprompt',ready)
  window.addEventListener('appinstalled',installed)
  if(window.isSecureContext && 'serviceWorker' in navigator && location.protocol!=='file:'){
   navigator.serviceWorker.register('/kingdom-sw.js').catch(()=>setMessage('Browser installation is unavailable. Kingdom still works in this tab.'))
  }
  return ()=>{window.removeEventListener('beforeinstallprompt',ready);window.removeEventListener('appinstalled',installed)}
 },[])
 const install=async()=>{
  const request=prompt;if(!request)return
  setPrompt(null)
  try{
   await request.prompt()
   const choice=await request.userChoice
   setMessage(choice.outcome==='accepted'?'Browser installation accepted.':'Installation cancelled. Nothing was installed.')
  }catch{setMessage('Installation did not finish. You can keep using this browser tab.')}
 }
 return <section aria-label="Install Kingdom web app">
  <p>Free web app: opens Kingdom in its own window. It needs a reachable Kingdom server; it does not install a local Windows backend or change certificate trust.</p>
  {prompt?<button type="button" onClick={install}>Install Kingdom web app</button>:<p className="muted">In Edge or Chrome, use the browser menu to install this site as an app when available. You can decline the browser confirmation.</p>}
  {message&&<p role="status">{message}</p>}
 </section>
}

import React,{useRef,useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

const emptyChat=()=>({profile:'auto',input:'',messages:[],busy:false,error:'',computer:''})
export default function ParallelChats(){
 const {data,error}=useLiveData('/workspace/model-profiles',10000)
 const [chats,setChats]=useState([emptyChat(),emptyChat()])
 const pending=useRef([false,false])
 const profiles=data?.profiles||[]
 const change=(index,patch)=>setChats(old=>old.map((chat,i)=>i===index?{...chat,...patch}:chat))
 const send=async(index,event)=>{
  event.preventDefault()
  const chat=chats[index],text=chat.input.trim()
  if(pending.current[index]||!text||!chat.profile)return
  if(chat.messages.length>=240){change(index,{error:'Clear this chat before starting a new conversation.'});return}
  pending.current[index]=true
  const messages=[...chat.messages,{role:'user',content:text}]
  change(index,{busy:true,error:'',messages,input:''})
  try{
   const {data:result}=await api.post(`/workspace/model-chat/${encodeURIComponent(chat.profile)}/chat/completions`,
    {messages,stream:false,max_tokens:1024,reasoning_effort:'none',temperature:0},{timeout:620000})
   const reply=result.choices?.[0]?.message?.content
   if(typeof reply!=='string'||!reply.trim())throw new Error('This model returned no chat text. Try another connection.')
   change(index,{messages:[...messages,{role:'assistant',content:reply}],computer:result.kingdom_profile||chat.profile})
  }catch(e){change(index,{messages:chat.messages,input:text,error:e.response?.data?.detail||e.message||'The model computer did not respond.'})}
  finally{pending.current[index]=false;change(index,{busy:false})}
 }
 return <section className="panel" aria-labelledby="parallel-chat-heading">
  <h2 id="parallel-chat-heading">Two model chats</h2>
  <p>Use different computers to run both chats at once. Connections on one computer share its request limit. Chats stay in this page until you clear them or leave it.</p>
  {error&&<p role="alert">Could not load model computers.</p>}
  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,280px),1fr))',gap:16}}>
   {chats.map((chat,index)=><section key={index} className="record-detail" style={{minWidth:0}} aria-label={`Chat ${index+1}`}>
    <h3>Chat {index+1}</h3>
    <label>Model computer<select style={{width:'100%',minWidth:0,maxWidth:'100%'}} value={chat.profile} disabled={chat.busy} onChange={e=>change(index,{profile:e.target.value,messages:[],computer:'',error:''})}>
     <option value="auto">Automatic · best available fit</option>
     {(data?.pools||[]).map(pool=><option key={`pool:${pool}`} value={`pool:${pool}`}>Pool {pool} · available computer</option>)}
     {profiles.map(p=><option key={p.id} value={p.id}>{p.id} · {p.model} · {p.computer_id||'Computer not associated'}</option>)}
    </select></label>
    <div aria-live="polite" style={{maxHeight:360,overflowY:'auto'}}>{chat.messages.map((message,i)=><div key={i}>
     <strong>{message.role==='user'?'You':'Model'}</strong><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{message.content}</pre>
    </div>)}</div>
    {chat.computer&&<p className="muted">Last reply from {chat.computer}</p>}
    {chat.error&&<p role="alert">{chat.error}</p>}
    <form onSubmit={event=>send(index,event)}>
     <label htmlFor={`model-chat-${index}`}>Message</label>
     <textarea id={`model-chat-${index}`} style={{width:'100%',boxSizing:'border-box'}} rows={4} maxLength={180000} value={chat.input} disabled={chat.busy}
      onChange={event=>change(index,{input:event.target.value})}/>
     <button disabled={chat.busy||!chat.profile||!chat.input.trim()}>{chat.busy?'Waiting for model…':`Send to chat ${index+1}`}</button>
     <button type="button" disabled={chat.busy} onClick={()=>change(index,{messages:[],error:'',computer:''})}>Clear chat</button>
    </form>
   </section>)}
  </div>
 </section>
}

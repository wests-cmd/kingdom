import React,{useEffect,useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import ConversationVoice from './ConversationVoice'

export default function UnifiedConversation(){
 const [scope,setScope]=useState(()=>localStorage.getItem('kingdom-conversation-scope')||crypto.randomUUID())
 const [project,setProject]=useState(()=>localStorage.getItem('kingdom-conversation-project')||'projects/default'),[prompt,setPrompt]=useState(''),[mode,setMode]=useState('auto'),[profile,setProfile]=useState('auto'),[allowProcess,setAllowProcess]=useState(false)
 const [selected,setSelected]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[key,setKey]=useState(()=>crypto.randomUUID())
 const {data:models}=useLiveData('/workspace/model-profiles',10000)
 const {data:requests,refresh}=useLiveData(`/requests?session_scope=${encodeURIComponent(scope)}&project_scope=${encodeURIComponent(project)}`,4000)
 useEffect(()=>localStorage.setItem('kingdom-conversation-scope',scope),[scope])
 useEffect(()=>localStorage.setItem('kingdom-conversation-project',project),[project])
 const current=(requests||[]).find(item=>item.id===selected)||null
 const run=async id=>{setBusy(true);setError('');try{await api.post(`/requests/${id}/run`,{},{timeout:620000})}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false);refresh()}}
 const submit=async event=>{event.preventDefault();setBusy(true);setError('');try{const {data}=await api.post('/requests',{idempotency_key:key,session_scope:scope,project_scope:project,prompt,mode,model_profile:profile,allow_process:allowProcess});setSelected(data.id);await refresh();await run(data.id);setKey(crypto.randomUUID());setPrompt('')}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false)}}
 return <section className="panel" style={{minWidth:0,overflowWrap:'anywhere'}}><h2>One conversation for questions and work</h2>
 <p>Automatic answers explicit time, runtime status and project-priority questions directly. Explicit workspace actions go to an agent; other questions use a model. You can also choose Quick model or Agent work directly.</p>
 {error&&<p role="alert">{error}</p>}
 <ConversationVoice onTranscript={setPrompt} answer={current?.answer||''} disabled={busy}/>
 <form onSubmit={submit}>
 <label>Project scope / workspace<input required value={project} disabled={busy} onChange={e=>{setProject(e.target.value);setSelected(null);setKey(crypto.randomUUID())}}/></label>
 <label>Request route<select value={mode} disabled={busy} onChange={e=>setMode(e.target.value)}><option value="auto">Automatic · deterministic first, then question or action</option><option value="quick">Quick model · text only</option><option value="agent">Agent work · workspace tools</option></select></label>
 <label>Model connection<select value={profile} disabled={busy} onChange={e=>setProfile(e.target.value)}><option value="auto">Automatic eligible model</option>{(models?.profiles||[]).map(item=><option value={item.id} key={item.id}>{item.id} · {item.model}</option>)}{(models?.pools||[]).map(pool=><option key={pool} value={`pool:${pool}`}>Pool {pool}</option>)}</select></label>
 <label>Your message<textarea required rows={4} maxLength={24000} disabled={busy} value={prompt} onChange={e=>setPrompt(e.target.value)} /></label>
 {mode==='agent'&&<label><input type="checkbox" checked={allowProcess} onChange={e=>setAllowProcess(e.target.checked)}/>Offer process tools, subject to existing grants and autonomy approvals</label>}
 <button disabled={busy||!prompt.trim()}>{busy?'Working…':'Send'}</button>
 </form>
 <details><summary>Reconnect another front door</summary><label>Conversation scope<input value={scope} disabled={busy} onChange={e=>{setScope(e.target.value);setSelected(null);setKey(crypto.randomUUID())}}/></label><p>Use the same conversation scope, project scope and idempotency key in another authenticated client to reconnect to the same request without duplicating work.</p></details>
 <label>Saved requests<select value={current?.id||''} onChange={e=>setSelected(e.target.value)}><option value="">Choose a saved request</option>{(requests||[]).map(item=><option key={item.id} value={item.id}>{item.prompt.slice(0,65)} · {item.status}</option>)}</select></label>
 {current&&<article><h3>{current.status.replaceAll('_',' ')} · {current.route}</h3><p>{current.prompt}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{current.answer||'No answer recorded yet.'}</pre>{current.error&&<p role="alert">{current.error}</p>}
 <p className="muted">Request {current.id} · model {current.model_profile}{current.agent_session_id?` · agent job ${current.agent_session_id}`:''}</p>
 {current.status==='running'&&<p>Work is in progress or has an interrupted checkpoint. Reconnecting never silently replays it. Inspect its agent job before cancelling and making a new request.</p>}
 <button disabled={busy||!['queued','waiting_review','ready'].includes(current.status)} onClick={()=>run(current.id)}>Continue saved request</button>
 <button disabled={['completed','cancelled','failed'].includes(current.status)} onClick={async()=>{try{await api.post(`/requests/${current.id}/cancel`);refresh()}catch(e){setError(e.message)}}}>Cancel further work</button>
 <details><summary>Progress and evidence</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(current.evidence,null,2)}</pre></details></article>}
 </section>
}

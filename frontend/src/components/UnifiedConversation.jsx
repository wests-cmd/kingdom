import React,{useEffect,useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import ConversationVoice from './ConversationVoice'
import AgentActivity from './AgentActivity'
import RequestShortcuts from './RequestShortcuts'

export default function UnifiedConversation({compact=false}){
 const [scope,setScope]=useState(()=>localStorage.getItem('kingdom-conversation-scope')||crypto.randomUUID())
 const [project,setProject]=useState(()=>localStorage.getItem('kingdom-conversation-project')||'projects/default'),[prompt,setPrompt]=useState(''),[mode,setMode]=useState('auto'),[profile,setProfile]=useState('auto'),[allowProcess,setAllowProcess]=useState(false)
 const [selected,setSelected]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[key,setKey]=useState(()=>crypto.randomUUID())
 const [desktopWindow,setDesktopWindow]=useState('')
 const [desktopExpected,setDesktopExpected]=useState('')
 const [backgroundSeconds,setBackgroundSeconds]=useState(310)
 const {data:models}=useLiveData('/workspace/model-profiles',10000)
 const {data:requests,error:historyError,refresh}=useLiveData(`/requests?session_scope=${encodeURIComponent(scope)}&project_scope=${encodeURIComponent(project)}`,4000)
 useEffect(()=>localStorage.setItem('kingdom-conversation-scope',scope),[scope])
 useEffect(()=>localStorage.setItem('kingdom-conversation-project',project),[project])
 // A late response from the previous scope must not render in this conversation.
 const history=(Array.isArray(requests)?requests:[]).filter(item=>item.session_scope===scope&&item.project_scope===project)
 const current=history.find(item=>item.id===selected)||history[0]||null
 const run=async id=>{setBusy(true);setError('');try{await api.post(`/requests/${id}/run`,{},{timeout:620000})}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false);refresh()}}
 const submit=async event=>{event.preventDefault();setBusy(true);setError('');try{const {data}=await api.post('/requests',{idempotency_key:key,session_scope:scope,project_scope:project,prompt,mode,model_profile:profile,allow_process:allowProcess,desktop_window_title:mode==='agent'?(desktopWindow||null):null,desktop_expected_text:mode==='agent'&&desktopWindow?(desktopExpected||null):null});setSelected(data.id);setKey(crypto.randomUUID());setPrompt('');if(data.route==='agent'){await api.post(`/requests/${data.id}/background`,{max_seconds:backgroundSeconds});await refresh()}else{await refresh();await run(data.id)}}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false)}}
 return <section className="panel" style={{minWidth:0,overflowWrap:'anywhere'}}><h2>{compact?'Quick Kingdom':'One conversation for questions and work'}</h2>
 <p>{compact?'Ask, review, and send. Closing this window does not stop server-owned background work.':'Ask questions or request work here. Saved turns follow this conversation when you switch model connections. Agent work uses the current objective and bounded prior conversation references; tools still require existing grants.'}</p>
 <p className="muted">Project: {project} · conversation {scope.slice(0,12)}</p>
 <section aria-label="Conversation history" style={{maxHeight:compact?220:520,overflowY:'auto',minWidth:0}}>
  {historyError&&<p role="status">History refresh failed. Showing only the last saved information for this conversation.</p>}
  {!history.length&&<p className="muted">{requests===null?'Loading saved conversation…':'Start a conversation with Kingdom.'}</p>}
  {[...history].reverse().map(item=><article key={item.id} className="record-detail" style={{marginBottom:12}}>
   <strong>You</strong><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{item.prompt}</p>
   <strong>Kingdom</strong><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{item.answer||'No answer recorded yet.'}</p>
   <p className="muted">{item.status.replaceAll('_',' ')} · {item.route}</p>
   <button type="button" onClick={()=>setSelected(item.id)}>Inspect work and evidence</button>
  </article>)}
 </section>
 {error&&<p role="alert">{error}</p>}
 <ConversationVoice onTranscript={setPrompt} answer={current?.answer||''} disabled={busy}/>
 <RequestShortcuts project={project} onDraft={value=>{setMode('auto');setPrompt(value);setKey(crypto.randomUUID())}} disabled={busy}/>
 <form onSubmit={submit} aria-label="Kingdom conversation composer">
 <details><summary>Advanced routing and workspace</summary>
 <label>Project scope / workspace<input required value={project} disabled={busy} onChange={e=>{setProject(e.target.value);setSelected(null);setKey(crypto.randomUUID())}}/></label>
 <label>Request route<select value={mode} disabled={busy} onChange={e=>setMode(e.target.value)}><option value="auto">Automatic · deterministic first, then question or action</option><option value="quick">Quick model · text only</option><option value="agent">Agent work · workspace tools</option></select></label>
 <label>Model connection<select value={profile} disabled={busy} onChange={e=>setProfile(e.target.value)}><option value="auto">Automatic eligible model</option>{(models?.profiles||[]).map(item=><option value={item.id} key={item.id}>{item.id} · {item.model}</option>)}{(models?.pools||[]).map(pool=><option key={pool} value={`pool:${pool}`}>Pool {pool}</option>)}</select></label>

 {mode!=='quick'&&<label>Background work limit<select disabled={busy} value={backgroundSeconds} onChange={e=>setBackgroundSeconds(Number(e.target.value))}><option value={60}>1 minute · short work</option><option value={310}>About 5 minutes · standard</option><option value={900}>15 minutes · slower local models</option><option value={1800}>30 minutes · longer local work</option></select><span>Applies to agent work. The limit includes model and tool waiting; it does not grant permissions or renew an exhausted request.</span></label>}
 {mode==='agent'&&<label><input type="checkbox" checked={allowProcess} onChange={e=>setAllowProcess(e.target.checked)}/>Offer process tools, subject to existing grants and autonomy approvals</label>}
 {mode==='agent'&&<details><summary>Let Kingdom use a Windows app</summary><p>Kingdom itself can observe, click, type and check the result in the exact foreground window you choose. Existing desktop grants still apply. Work runs on your Kingdom server while this page is closed.</p><label>Exact foreground window title<input maxLength={500} disabled={busy} value={desktopWindow} onChange={e=>setDesktopWindow(e.target.value)} placeholder="Leave empty to keep computer use off"/></label><label>What visible text proves it worked?<input maxLength={2000} disabled={busy} value={desktopExpected} onChange={e=>setDesktopExpected(e.target.value)} placeholder="Optional exact text Kingdom must actually observe"/></label></details>}
 </details>
 <label>Your message<textarea aria-label="Your message" required rows={compact?3:4} maxLength={24000} disabled={busy} value={prompt} onChange={e=>setPrompt(e.target.value)} /></label>
 <button disabled={busy||!prompt.trim()}>{busy?'Working…':'Send'}</button>
 </form>
 <details><summary>Reconnect another front door</summary><label>Conversation scope<input value={scope} disabled={busy} onChange={e=>{setScope(e.target.value);setSelected(null);setKey(crypto.randomUUID())}}/></label><p>Use the same conversation scope, project scope and idempotency key in another authenticated client to reconnect to the same request without duplicating work.</p></details>
 <h3>Selected work and evidence</h3>
 {current?.agent_session_id&&<AgentActivity jobId={current.agent_session_id}/>}
 {current&&<article><h3>{current.status.replaceAll('_',' ')} · {current.route}</h3><p>{current.prompt}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{current.answer||'No answer recorded yet.'}</pre>{current.error&&<p role="alert">{current.error}</p>}
 <p className="muted">Request {current.id} · model {current.model_profile}{current.agent_session_id?` · agent job ${current.agent_session_id}`:''}</p>
 {current.status==='running'&&<p>Work is in progress or has an interrupted checkpoint. Reconnecting never silently replays it. Inspect its agent job before cancelling and making a new request.</p>}
 <button disabled={busy||!['queued','waiting_review','ready'].includes(current.status)} onClick={()=>run(current.id)}>Continue saved request</button>
 <button disabled={['completed','cancelled','failed'].includes(current.status)} onClick={async()=>{try{await api.post(`/requests/${current.id}/cancel`);refresh()}catch(e){setError(e.message)}}}>Cancel further work</button>
 <details><summary>Progress and evidence</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(current.evidence,null,2)}</pre></details></article>}
 </section>
}

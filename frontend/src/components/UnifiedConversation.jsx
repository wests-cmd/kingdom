import React,{useEffect,useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import ConversationVoice from './ConversationVoice'
import AgentActivity from './AgentActivity'
import RequestShortcuts from './RequestShortcuts'
import ScreenRegion from './ScreenRegion'

function GovernedProgress({requestId}){
 const {data}=useLiveData('/requests/'+encodeURIComponent(requestId)+'/progress',3000)
 const recent=data?.progress?.[0]
 return <p role="status">Task: {data?.status||'Checking retained status'}{recent?' · '+recent.bytes+' output bytes · '+recent.elapsed_seconds+' seconds (not completion evidence)':''}</p>
}

export default function UnifiedConversation({compact=false}){
 const [scope,setScope]=useState(()=>localStorage.getItem('kingdom-conversation-scope')||crypto.randomUUID())
 const [project,setProject]=useState(()=>localStorage.getItem('kingdom-conversation-project')||'projects/default'),[prompt,setPrompt]=useState(''),[mode,setMode]=useState('auto'),[profile,setProfile]=useState('auto'),[allowProcess,setAllowProcess]=useState(false)
 const [selected,setSelected]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[key,setKey]=useState(()=>crypto.randomUUID())
 const [harness,setHarness]=useState(''),[fallback,setFallback]=useState(''),[region,setRegion]=useState(null),[group,setGroup]=useState(''),[knight,setKnight]=useState(''),[learnName,setLearnName]=useState('')
 const [measured,setMeasured]=useState(false),[benchmarkProfile,setBenchmarkProfile]=useState(''),[benchmarkResult,setBenchmarkResult]=useState(null)
 const [guide,setGuide]=useState(false),[captureRevision,setCaptureRevision]=useState(0),[shortcutRevision,setShortcutRevision]=useState(0)
 const clearRegion=()=>{setRegion(null);setGuide(false);setCaptureRevision(v=>v+1)}
 const resetScopeDraft=()=>{clearRegion();setPrompt('');setFallback('');setAllowProcess(false);setDesktopWindow('');setDesktopExpected('');setSelected(null);setKey(crypto.randomUUID())}
 const [desktopWindow,setDesktopWindow]=useState('')
 const [desktopExpected,setDesktopExpected]=useState('')
 const [backgroundSeconds,setBackgroundSeconds]=useState(310)
 const {data:models}=useLiveData('/workspace/model-profiles',10000)
 const {data:harnesses}=useLiveData('/harnesses',null)
 const {data:teams}=useLiveData('/hierarchy',null)
 const {data:requests,error:historyError,refresh}=useLiveData(`/requests?session_scope=${encodeURIComponent(scope)}&project_scope=${encodeURIComponent(project)}`,4000)
 useEffect(()=>localStorage.setItem('kingdom-conversation-scope',scope),[scope])
 useEffect(()=>localStorage.setItem('kingdom-conversation-project',project),[project])
 // A late response from the previous scope must not render in this conversation.
 const history=(Array.isArray(requests)?requests:[]).filter(item=>item.session_scope===scope&&item.project_scope===project)
 const current=history.find(item=>item.id===selected)||history[0]||null
 const run=async id=>{setBusy(true);setError('');try{await api.post(`/requests/${id}/run`,{},{timeout:620000})}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false);refresh()}}
 const submit=async event=>{event.preventDefault();setBusy(true);setError('');try{const {data}=await api.post('/requests',{idempotency_key:key,session_scope:scope,project_scope:project,prompt,mode,model_profile:profile,allow_process:['agent','harness'].includes(mode)&&allowProcess,prefer_benchmarked:mode==='quick'&&profile==='auto'&&!region&&measured,harness_id:mode==='harness'?(harness||null):null,fallback_profile:mode==='quick'&&!region&&profile!=='auto'&&!profile.startsWith('pool:')?(fallback||null):null,screen_region:mode==='quick'?region:null,guide_region:mode==='quick'&&Boolean(region)&&guide,group_id:['delegate','commander'].includes(mode)?(group||null):null,target_knight:mode==='delegate'?(knight||null):null,desktop_window_title:mode==='agent'?(desktopWindow||null):null,desktop_expected_text:mode==='agent'&&desktopWindow?(desktopExpected||null):null});setSelected(data.id);setKey(crypto.randomUUID());setPrompt('');clearRegion();if(data.route==='agent'){await api.post(`/requests/${data.id}/background`,{max_seconds:backgroundSeconds});await refresh()}else{await refresh();await run(data.id)}}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false)}}
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
 <ConversationVoice key={scope+'|'+project} onTranscript={setPrompt} answer={current?.answer||''} disabled={busy}/>
 <RequestShortcuts key={project+'|'+shortcutRevision} project={project} onDraft={value=>{setMode('auto');clearRegion();setPrompt(value);setKey(crypto.randomUUID())}} disabled={busy}/>
 <details><summary>Measure a model connection</summary><p>Send three synthetic prompts to one explicitly selected provider. This may consume its quota or incur provider charges. No conversation history is sent. Results measure only this small text suite.</p><select aria-label="Benchmark model" value={benchmarkProfile} disabled={busy} onChange={e=>setBenchmarkProfile(e.target.value)}><option value="">Select a configured model</option>{(models?.profiles||[]).filter(p=>!p.disabled).map(p=><option key={p.id} value={p.id}>{p.id}</option>)}</select><button type="button" disabled={busy||!benchmarkProfile} onClick={async()=>{setBusy(true);setBenchmarkResult(null);try{const {data}=await api.post('/requests/benchmarks',{profile:benchmarkProfile},{timeout:150000});setBenchmarkResult(data)}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false)}}}>Run three synthetic tests</button>{benchmarkResult&&<p>{benchmarkResult.profile}: {benchmarkResult.passed}/{benchmarkResult.total} exact answers, mean {benchmarkResult.latency_ms} ms.</p>}</details>
 <ScreenRegion key={scope+'|'+project+'|'+captureRevision} disabled={busy} onRegion={value=>{setRegion(value);if(value){setMode('quick');setFallback('');setAllowProcess(false)}}}/>
 {region&&<><p role="status">Reviewed crop attached. Select an explicit vision model; only this crop and question are sent, and the crop is retained in the saved request.</p><label><input type="checkbox" checked={guide} disabled={busy} onChange={e=>setGuide(e.target.checked)}/>Ask for visual teaching marks on this snapshot</label></>}
 <form onSubmit={submit} aria-label="Kingdom conversation composer">
 <details><summary>Advanced routing and workspace</summary>
 <label>Project scope / workspace<input required value={project} disabled={busy} onChange={e=>{setProject(e.target.value);resetScopeDraft()}}/></label>
 <label>Request route<select value={mode} disabled={busy} onChange={e=>{setMode(e.target.value);clearRegion();setAllowProcess(false)}}><option value="auto">Automatic · deterministic first, then question or action</option><option value="quick">Quick model · text only</option><option value="agent">Agent work · workspace tools</option><option value="harness">Configured harness · approved process</option><option value="delegate">Delegate text analysis to a Knight</option><option value="commander">Commander · draft a multi-Knight analysis mission</option></select></label>
 <label>Model connection<select value={profile} disabled={busy} onChange={e=>{setProfile(e.target.value);setFallback('')}}><option value="auto">Automatic eligible model</option>{(models?.profiles||[]).map(item=><option value={item.id} key={item.id}>{item.id} · {item.model}</option>)}{(models?.pools||[]).map(pool=><option key={pool} value={`pool:${pool}`}>Pool {pool}</option>)}</select></label>

 {mode==='quick'&&!region&&profile==='auto'&&<label><input type="checkbox" checked={measured} disabled={busy} onChange={e=>setMeasured(e.target.checked)}/>Prefer a reachable model with a fresh passing synthetic text benchmark</label>}
 {mode==='quick'&&!region&&<label>Optional fallback on incomplete text answer<select value={fallback} disabled={busy||profile==='auto'||profile.startsWith('pool:')} onChange={e=>setFallback(e.target.value)}><option value="">None</option>{(models?.profiles||[]).filter(p=>p.id!==profile&&!p.disabled).map(p=><option key={p.id} value={p.id}>{p.id}</option>)}</select><span>One extra inference on the selected provider, only for an incomplete response. Both providers may receive conversation context. No fallback after a permission or transport error.</span></label>}
 {mode==='harness'&&<label>Configured harness<select required value={harness} disabled={busy} onChange={e=>setHarness(e.target.value)}><option value="">Choose a connection</option>{(harnesses?.profiles||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><span>Exact process approval still applies; the external harness is not an OS sandbox.</span></label>}
 {['delegate','commander'].includes(mode)&&<><label>Local team<select required value={group} disabled={busy||teams?.groups_shared} onChange={e=>{setGroup(e.target.value);setKnight('')}}><option value="">Choose a group</option>{(teams?.groups||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>{mode==='delegate'&&<label>Member Knight<select required value={knight} disabled={busy||teams?.groups_shared} onChange={e=>setKnight(e.target.value)}><option value="">Choose a Knight</option>{(teams?.groups||[]).find(p=>p.id===group)?.members?.map(id=><option key={id} value={id}>{id}</option>)}</select></label>}<p>Text and Python analysis only. Shared groups must use their authority controller. Commander drafts require review and exact-version approval in Missions before any work.</p></>}
 {['auto','agent'].includes(mode)&&<label>Background work limit<select disabled={busy} value={backgroundSeconds} onChange={e=>setBackgroundSeconds(Number(e.target.value))}><option value={60}>1 minute · short work</option><option value={310}>About 5 minutes · standard</option><option value={900}>15 minutes · slower local models</option><option value={1800}>30 minutes · longer local work</option></select><span>Applies to agent work. The limit includes model and tool waiting; it does not grant permissions or renew an exhausted request.</span></label>}
 {['agent','harness'].includes(mode)&&<label><input type="checkbox" checked={allowProcess} onChange={e=>setAllowProcess(e.target.checked)}/>Offer process tools, subject to existing grants and autonomy approvals</label>}
 {mode==='agent'&&<details><summary>Let Kingdom use a Windows app</summary><p>Kingdom itself can observe, click, type and check the result in the exact foreground window you choose. Existing desktop grants still apply. Work runs on your Kingdom server while this page is closed.</p><label>Exact foreground window title<input maxLength={500} disabled={busy} value={desktopWindow} onChange={e=>setDesktopWindow(e.target.value)} placeholder="Leave empty to keep computer use off"/></label><label>What visible text proves it worked?<input maxLength={2000} disabled={busy} value={desktopExpected} onChange={e=>setDesktopExpected(e.target.value)} placeholder="Optional exact text Kingdom must actually observe"/></label></details>}
 </details>
 <label>Your message<textarea aria-label="Your message" required rows={compact?3:4} maxLength={24000} disabled={busy} value={prompt} onChange={e=>setPrompt(e.target.value)} /></label>
 <button disabled={busy||!prompt.trim()||(mode==='harness'&&(!harness||!allowProcess))||(['delegate','commander'].includes(mode)&&(!group||(mode==='delegate'&&!knight)||teams?.groups_shared))||(region&&(mode!=='quick'||!(models?.profiles||[]).some(p=>p.id===profile&&p.vision&&!p.disabled))) }>{busy?'Working…':'Send'}</button>
 </form>
 <details><summary>Reconnect another front door</summary><label>Conversation scope<input value={scope} disabled={busy} onChange={e=>{setScope(e.target.value);resetScopeDraft()}}/></label><p>Use the same conversation scope, project scope and idempotency key in another authenticated client to reconnect to the same request without duplicating work.</p></details>
 <h3>Selected work and evidence</h3>
 {current?.governed_mission_id&&<p>Commander mission: {current.governed_mission_id}. Inspect the proposed steps under Progress and evidence; approve the exact reviewed version under Missions. Continue saved request retrieves its current report.</p>}
 {current?.governed_task_id&&<><p>Linked task: {current.governed_task_id} · inspect approval and progress under Tasks.</p><GovernedProgress key={current.id} requestId={current.id}/></>}
 {current?.agent_session_id&&<AgentActivity jobId={current.agent_session_id}/>}
 {current&&<article><h3>{current.status.replaceAll('_',' ')} · {current.route}</h3><p>{current.prompt}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{current.answer||'No answer recorded yet.'}</pre>{current.error&&<p role="alert">{current.error}</p>}
 <p className="muted">Request {current.id} · model {current.model_profile}{current.agent_session_id?` · agent job ${current.agent_session_id}`:''}</p>
 {current.status==='running'&&<p>Work is in progress or has an interrupted checkpoint. Reconnecting never silently replays it. Inspect its agent job before cancelling and making a new request.</p>}
 <button disabled={busy||!['queued','waiting_review','ready'].includes(current.status)} onClick={()=>run(current.id)}>Continue saved request</button>
 <button disabled={['completed','cancelled','failed'].includes(current.status)} onClick={async()=>{try{await api.post(`/requests/${current.id}/cancel`);refresh()}catch(e){setError(e.message)}}}>Cancel further work</button>
 {current.status==='completed'&&['time','status','priorities','work','help','harnesses'].includes(current.route)&&<div><label>Learn this verified instant command<input maxLength={40} value={learnName} onChange={e=>setLearnName(e.target.value)} placeholder="e.g. focus"/></label><button type="button" disabled={busy||!learnName.trim()} onClick={async()=>{try{await api.post('/requests/shortcuts/learn',{name:learnName,request_id:current.id,session_scope:scope,project_scope:project});setLearnName('');setShortcutRevision(v=>v+1);setError('');refresh()}catch(e){setError(e.response?.data?.detail||e.message)}}}>Save from verified result</button></div>}
 {current.screen_region&&current.evidence?.some(e=>e.type==='visual_guidance')&&<div><p>Advisory teaching marks on the retained snapshot. The screen may have changed; no input was sent.</p><div style={{position:'relative',display:'inline-block',maxWidth:'100%'}}><img src={current.screen_region} alt="Reviewed snapshot with suggested teaching marks" style={{display:'block',maxWidth:'100%'}}/>{current.evidence.find(e=>e.type==='visual_guidance').annotations.map((mark,i)=><div key={i} style={{position:'absolute',left:mark.x+'%',top:mark.y+'%',width:mark.w+'%',height:mark.h+'%',border:'2px solid #ff5252',boxSizing:'border-box',pointerEvents:'none'}}><span style={{background:'#220d15',color:'#fff',fontSize:12}}>{i+1}</span></div>)}</div><ol>{current.evidence.find(e=>e.type==='visual_guidance').annotations.map((mark,i)=><li key={i}>{mark.label}</li>)}</ol></div>}
 {current.route==='harness'&&current.status==='completed'&&current.evidence?.some(e=>e.type==='harness_proposals'&&e.proposals.length>0)&&<button type="button" disabled={busy} onClick={async()=>{try{const {data}=await api.post('/requests/'+current.id+'/review-harness-proposals');setError('Unapproved mission draft '+data.id+' created. Review in Missions before execution.')}catch(e){setError(e.response?.data?.detail||e.message)}}}>Review supported harness proposals as a new mission</button>}
 <details><summary>Progress and evidence</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(current.evidence,null,2)}</pre></details></article>}
 </section>
}

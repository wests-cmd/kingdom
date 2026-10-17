import React,{useState,useEffect} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import UnifiedConversation from '../components/UnifiedConversation'
import HarnessQuickConnect from '../components/HarnessQuickConnect'
import ModelProfiles from '../components/ModelProfiles'

export default function Workbench(){
 const {data:sessions,refresh}=useLiveData('/agent-sessions',5000)
 const {data:models}=useLiveData('/workspace/model-profiles',10000)
 const {data:harnesses,refresh:refreshHarnesses}=useLiveData('/harnesses',10000)
 const {data:nodes}=useLiveData('/service-nodes',10000)
 const {data:skills}=useLiveData('/skill-documents',10000)
 const [skillIds,setSkillIds]=useState([])
 const [workspace,setWorkspace]=useState('projects/default')
 const [knowledgeScope,setKnowledgeScope]=useState(''),[embeddingProfile,setEmbeddingProfile]=useState(''),[ownerMemory,setOwnerMemory]=useState(false)
 const [observed,setObserved]=useState({})
 const [objective,setObjective]=useState(''),[profile,setProfile]=useState('auto'),[allowProcess,setAllowProcess]=useState(false)
 const [selected,setSelected]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const [connection,setConnection]=useState({id:'',name:'',kind:'custom-cli',argv:'["/absolute/path/to/agent", "{prompt}"]',environment:'{}',timeout_seconds:600})
 const [harness,setHarness]=useState(''),[job,setJob]=useState(''),[cwd,setCwd]=useState('.'),[task,setTask]=useState(null)
 const perform=async fn=>{setBusy(true);setError('');try{await fn()}catch(e){setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:e.message)}finally{setBusy(false)}}
 const current=(sessions||[]).find(s=>s.id===selected?.id)||selected
 const [readiness,setReadiness]=useState(null),[review,setReview]=useState(''),[requireEdit,setRequireEdit]=useState(false)
 useEffect(()=>{if(profile==='auto'||!models?.profiles?.length)return;const valid=models.profiles.some(p=>p.id===profile)||(profile.startsWith('pool:')&&models.pools?.includes(profile.slice(5)));if(!valid)setProfile(models.profiles.find(p=>p.id==='this-pc')?.id||models.profiles.find(p=>p.id==='laptop3')?.id||models.profiles[0].id)},[models,profile])
 return <div className="page"><h1>Agent workbench</h1>
  <section className="panel"><h2>Coding setup</h2><button disabled={busy} onClick={()=>perform(async()=>{const {data}=await api.get('/agent-sessions/readiness');setReadiness(data)})}>Check coding setup without inference</button>{readiness&&<div><p>{readiness.ready_for_scoped_file_work?'Workspace coding setup is ready. Independent tests are still required.':'Coding setup needs attention.'}</p>{readiness.blockers.map(reason=><p key={reason} role="alert">{reason}</p>)}{readiness.models.map(model=><p key={model.id}>{model.id} · {model.model} · {model.computer || 'Host not labeled'}</p>)}</div>}</section>
  <p>Give a model a job with real workspace tools, or hand the job to an installed agent such as Hermes or Claude. You keep control of permissions and approvals.</p>
  {error&&<p role="alert">{error}</p>}
  <UnifiedConversation />
  <section className="panel"><h2>Work with a model</h2>
   <p>Conversations and tool evidence are saved. Model inference runs on your selected computer; workspace tools run on the Kingdom host.</p>
   <form onSubmit={e=>{e.preventDefault();perform(async()=>{const {data}=await api.post('/agent-sessions',{objective,model_profile:profile,max_turns:12,allow_process:allowProcess,skill_ids:skillIds,workspace,knowledge_scope:knowledgeScope||null,embedding_profile:embeddingProfile||null,use_owner_memory:ownerMemory,required_tools:requireEdit?['workspace_read','workspace_write']:[]});setSelected(data);refresh()})}}>
    <label>Model computer<select value={profile} onChange={e=>setProfile(e.target.value)}><option value="auto">Automatic · available model that fits this request</option>{(models?.profiles||[]).map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}{(models?.pools||[]).map(p=><option key={p} value={`pool:${p}`}>Pool {p}</option>)}</select></label>
    <label>What should it do?<textarea required rows={5} maxLength={24000} value={objective} onChange={e=>setObjective(e.target.value)} placeholder="Inspect the workspace and implement a small change. Run checks and report what actually passed."/></label>
    <label><input type="checkbox" checked={requireEdit} onChange={e=>setRequireEdit(e.target.checked)}/>Require verified source read and edit before this job can complete</label>
    <label>Project folder<input required value={workspace} onChange={e=>setWorkspace(e.target.value)}/></label>
    <details><summary>Knowledge references</summary><p>Save documents under Memory first. Choose the same scope and embedding connection; other scopes stay out of vector retrieval.</p><label>Knowledge scope<input value={knowledgeScope} onChange={e=>setKnowledgeScope(e.target.value)}/></label><label>Embedding connection<select value={embeddingProfile} onChange={e=>setEmbeddingProfile(e.target.value)}><option value="">No vector retrieval</option>{(models?.profiles||[]).map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}</select></label><label><input type="checkbox" checked={ownerMemory} onChange={e=>setOwnerMemory(e.target.checked)}/>Also use shared owner memory across projects</label></details>
    <label><input type="checkbox" checked={allowProcess} onChange={e=>setAllowProcess(e.target.checked)}/>Offer command execution to this model. Individual approval is required at levels 1–4; level 5 uses your standing authorization and existing tool grants.</label>
    <details><summary>Use saved skill instructions</summary><p>Import documents in Skill maps &amp; Discord first. Selected instructions stay untrusted and do not grant tools.</p>{(skills||[]).map(skill=><label key={skill.skill_id}><input type="checkbox" checked={skillIds.includes(skill.skill_id)} onChange={e=>setSkillIds(old=>e.target.checked?[...old,skill.skill_id]:old.filter(id=>id!==skill.skill_id))}/>{skill.name}</label>)}</details>
    <button disabled={busy||!objective.trim()}>Create saved job</button>
   </form>
   <label>Saved jobs<select value={current?.id||''} onChange={e=>setSelected((sessions||[]).find(s=>s.id===e.target.value)||null)}><option value="">Choose a job</option>{(sessions||[]).map(s=><option key={s.id} value={s.id}>{s.objective.slice(0,65)} · {s.status}</option>)}</select></label>
   {current&&<div><h3>{current.status.replaceAll('_',' ')}</h3><p>Model turns: {current.turns}/{current.max_turns}</p>
    {current.error&&<p role="alert">{current.error}</p>}
    {['needs_review','completed'].includes(current.status)&&<div><label>Reviewed correction or independent test failure<textarea maxLength={4000} value={review} onChange={e=>setReview(e.target.value)}/></label><button disabled={busy||!review.trim()} onClick={()=>perform(async()=>{const {data}=await api.post(`/agent-sessions/${current.id}/review-feedback`,{message:review,expected_updated_at:current.updated_at});setSelected(data);setReview('');refresh()})}>Save reviewed correction</button><p className="muted">Preserves the conversation and turn budget. Failed writes, processes and approval decisions cannot be replayed through this control.</p></div>}
    <p>Start Runtime if it is stopped. Grant the intended Apprentice file capabilities in Governance. Review pending operations there, then continue this job.</p>
    <button disabled={busy||['completed','cancelled','needs_review','budget_exhausted'].includes(current.status)} onClick={()=>perform(async()=>{const {data}=await api.post(`/agent-sessions/${current.id}/advance`,{},{timeout:620000});setSelected(data);refresh()})}>{busy?'Working…':'Continue one step'}</button>
    <button disabled={busy||['completed','cancelled','needs_review','budget_exhausted'].includes(current.status)} onClick={()=>perform(async()=>{const {data}=await api.post(`/agent-sessions/${current.id}/run`,{max_turns:2,max_seconds:300},{timeout:320000});setSelected(data);refresh()})}>Run until review or budget</button>
    <button disabled={current.status==='cancelled'} onClick={async()=>{try{const {data}=await api.post(`/agent-sessions/${current.id}/cancel`);setSelected(data);refresh()}catch(e){setError(e.message)}}}>Cancel job</button>
    {(current.pending||[]).map(p=><p key={p.task_id}>Pending {p.name}: task {p.task_id}</p>)}
    <div style={{maxHeight:420,overflow:'auto'}}>{current.messages.filter(m=>m.role!=='system').map((m,i)=><div key={i}><strong>{m.role}</strong><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{m.content||JSON.stringify(m.tool_calls,null,2)}</pre></div>)}</div>
   </div>}
  </section>
  <section className="panel"><h2>Delegate to an installed harness</h2><p>{harnesses?.notice}</p>
   <HarnessQuickConnect onSaved={refreshHarnesses}/>
   <details><summary>Connect a cloud or local API model</summary><p>Use a provider implementing the supported chat API. This does not connect arbitrary service APIs or carry over a chat website subscription automatically.</p><ModelProfiles/></details>
   <form onSubmit={e=>{e.preventDefault();perform(async()=>{const {data}=await api.post(`/harnesses/${encodeURIComponent(harness)}/jobs`,{prompt:job,cwd});setTask(data)})}}>
    <label>Agent connection<select required value={harness} onChange={e=>setHarness(e.target.value)}><option value="">Choose an agent</option>{(harnesses?.profiles||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <label>Job<textarea required maxLength={4000} rows={4} value={job} onChange={e=>setJob(e.target.value)}/></label>
    <label>Workspace folder<input value={cwd} onChange={e=>setCwd(e.target.value)}/></label>
    <button disabled={busy||!harness}>Queue job for approval</button>
   </form>{task&&<p role="status">Task {task.id} queued. Follow it in Tasks and approve its exact invocation in Governance.</p>}
   <details><summary>Add an agent connection</summary><p>Use its installed executable and documented noninteractive arguments. Windows command scripts need an explicit launcher. These are host processes, not sandboxed agents. Keep secrets in the agent's credential store.</p>
    <form onSubmit={e=>{e.preventDefault();perform(async()=>{const {id,argv,environment,...rest}=connection;await api.put(`/harnesses/${encodeURIComponent(id)}`,{...rest,argv:JSON.parse(argv),environment:JSON.parse(environment)});refreshHarnesses()})}}>
     <label>Connection ID<input required pattern="[a-z][a-z0-9_-]{0,63}" value={connection.id} onChange={e=>setConnection({...connection,id:e.target.value})}/></label>
     <label>Name<input required value={connection.name} onChange={e=>setConnection({...connection,name:e.target.value})}/></label>
     <label>Argument list (JSON)<textarea rows={5} value={connection.argv} onChange={e=>setConnection({...connection,argv:e.target.value})}/></label>
     <label>Configuration paths (JSON)<textarea value={connection.environment} onChange={e=>setConnection({...connection,environment:e.target.value})}/></label>
     <label>Timeout in seconds<input type="number" min={1} max={1800} value={connection.timeout_seconds} onChange={e=>setConnection({...connection,timeout_seconds:Number(e.target.value)})}/></label><button disabled={busy}>Save connection</button>
    </form>
   </details>
  </section>
  <section className="panel"><h2>Connected services</h2><p>Inspect running services on registered computers. Actions become exact tasks for approval; the service keeps its existing deployment.</p>
   {(nodes||[]).map(node=><div className="record-detail" key={node.id}><h3>{node.name}</h3><button disabled={busy} onClick={()=>perform(async()=>{const {data}=await api.get(`/service-nodes/${node.id}/inspect`,{timeout:25000});setObserved(old=>({...old,[node.id]:data.services}))})}>Refresh service status</button>
    {(observed[node.id]||[]).map(unit=><div key={unit.Id}><p>{unit.Description||unit.Id}: {unit.ActiveState} / {unit.SubState}</p>{['start','stop','restart'].map(action=><button key={action} disabled={busy} onClick={()=>perform(async()=>{const {data}=await api.post(`/service-nodes/${node.id}/actions`,{unit:unit.Id,action});setTask(data)})}>Request {action}</button>)}</div>)}
   </div>)}
  </section>
 </div>
}



import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
export default function DurableSchedulesPanel(){
 const [project,setProject]=useState('default'),[prompt,setPrompt]=useState(''),[minutes,setMinutes]=useState(60),[mode,setMode]=useState('agent'),[profile,setProfile]=useState('auto'),[review,setReview]=useState('Review execution evidence and tests before continuing.'),[enabled,setEnabled]=useState(false),[autorun,setAutorun]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[receipts,setReceipts]=useState({})
 const valid=/^[A-Za-z0-9_-]{1,80}$/.test(project)
 const {data,error:readError,refresh}=useLiveData(valid?`/automations/schedules/${encodeURIComponent(project)}`:'/automations/schedules/default',10000)
 const {data:models}=useLiveData('/workspace/model-profiles',10000)
 const perform=async operation=>{setBusy(true);setError('');setMessage('');try{await operation();await refresh()}catch(e){setError(e.response?.data?.detail||e.message)}finally{setBusy(false)}}
 const change=async(item,status)=>perform(async()=>{await api.post(`/automations/schedules/${encodeURIComponent(project)}/${item.id}/status`,{status,expected_revision:item.revision});setMessage('Schedule updated against its current revision.')})
 return <section className="panel" style={{minWidth:0,overflowWrap:'anywhere'}}><h2>Scheduled project work</h2><p>Create recurring saved requests for a project. Each due run creates a saved request. Choose automatic bounded work only when intended; it requires autonomy level 4 or 5 and retains existing tool approvals. New schedules start paused unless you enable them.</p>
 {(error||readError)&&<p role="alert">{error||readError}</p>}{message&&<p role="status">{message}</p>}{busy&&<p role="status">Updating scheduled work…</p>}
 <label>Project name<input required pattern="[A-Za-z0-9_-]{1,80}" maxLength={80} value={project} disabled={busy} onChange={e=>{setProject(e.target.value);setReceipts({})}}/></label><p className="muted">Requests use workspace scope projects/{project||'…'}. Use a short project name, without slashes.</p>
 <form onSubmit={e=>{e.preventDefault();perform(async()=>{await api.post('/automations/schedules/work',{project,prompt,interval_sec:Number(minutes)*60,mode,model_profile:profile,review_instructions:review,enabled,autorun});setPrompt('');setEnabled(false);setAutorun(false);setMessage('Work schedule saved. Inspect its state and receipts below.')})}}>
 <label>What should be reviewed or worked on?<textarea required rows={4} maxLength={20000} value={prompt} onChange={e=>setPrompt(e.target.value)}/></label>
 <label>Repeat every (minutes)<input type="number" required min={1} max={43200} step={1} value={minutes} onChange={e=>setMinutes(e.target.value)}/></label>
 <label>Request route<select value={mode} onChange={e=>setMode(e.target.value)}><option value="agent">Agent work</option><option value="quick">Quick model question</option><option value="auto">Automatic</option></select></label>
 <label>Model connection<select value={profile} onChange={e=>setProfile(e.target.value)}><option value="auto">Automatic eligible model</option>{(models?.profiles||[]).map(item=><option value={item.id} key={item.id}>{item.id} · {item.model}</option>)}{(models?.pools||[]).map(pool=><option key={pool} value={`pool:${pool}`}>Pool {pool}</option>)}</select></label>
 <label>Review instructions<textarea rows={2} maxLength={2000} value={review} onChange={e=>setReview(e.target.value)}/></label>
 <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Enable recurring request creation now</label>
 <label><input type="checkbox" checked={autorun} onChange={e=>setAutorun(e.target.checked)}/>Run bounded jobs automatically at autonomy level 4 or 5</label><p className="muted">Leave automatic work off to queue requests for manual review. Automatic runs stop at their execution budget or an approval boundary.</p>
 <button disabled={busy||!valid||!prompt.trim()}>Save {enabled?'enabled':'paused'} schedule</button></form>
 {!valid?<p>Enter a valid project name to inspect schedules.</p>:!data?<p>Loading schedules…</p>:!(data.schedules||[]).length?<p>No schedules saved for this project.</p>:(data.schedules||[]).map(item=><article className="record-detail" key={item.id}>
 <h3>{item.operation==='enqueue_request'?'Recurring work request':'Recurring project note'}</h3><p><strong>{item.status}</strong> · every {Math.round(item.interval_sec/60)} minutes · revision {item.revision}</p><p>Next due: {new Date(item.next_due*1000).toLocaleString()}{item.status!=='active'?' (paused or cancelled; will not run)':''}</p>
 {item.model_profile&&<p>Model: {item.model_profile} · route: {item.mode} · workspace: {item.project_scope}</p>}
 <p className="muted">{item.autorun?'Automatic bounded work requested; autonomy and existing approval checks still apply.':'This schedule queues requests for manual review.'} A queue receipt proves request creation, not successful execution.</p>
 <div style={{display:'flex',flexWrap:'wrap',gap:8}}><button disabled={busy||item.status==='active'||item.status==='cancelled'} onClick={()=>change(item,'active')}>Enable</button><button disabled={busy||item.status!=='active'} onClick={()=>change(item,'paused')}>Pause</button><button disabled={busy||item.status==='cancelled'} onClick={()=>change(item,'cancelled')}>Cancel schedule</button><button disabled={busy} onClick={()=>perform(async()=>{const {data}=await api.get(`/automations/schedules/${project}/${item.id}/receipts`);setReceipts(old=>({...old,[item.id]:data.receipts}))})}>Read receipts</button></div>
 <details><summary>Latest checkpoint and saved receipts</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({checkpoint:item.checkpoint,receipts:receipts[item.id]||[]},null,2)}</pre></details>
 </article>)}
 <button disabled={busy||!valid} onClick={()=>perform(async()=>{await refresh();setMessage('Schedule state refreshed.')})}>Refresh schedules</button>
 </section>
}

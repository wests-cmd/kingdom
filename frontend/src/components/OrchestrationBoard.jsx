import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

const label = value => String(value || 'Not reported').replaceAll('_',' ')
export default function OrchestrationBoard() {
 const {data,error,updated,refresh}=useLiveData('/orchestration',5000)
 const [filter,setFilter]=useState('attention'),[actionError,setActionError]=useState(''),[busy,setBusy]=useState('')
 const jobs=data?.jobs || []
 const running=jobs.filter(j=>j.status==='running')
 const visible=jobs.filter(j=>filter==='all' || (filter==='done' ? j.status==='completed' : !['completed','cancelled'].includes(j.status)))
 async function start(id) {
  setBusy(id);setActionError('')
  try {await api.post(`/requests/${id}/background`); await refresh()}
  catch(e) {setActionError(e.response?.data?.detail || 'Could not start background work.')}
  finally {setBusy('')}
 }
 return <section className="panel orchestration-board" aria-label="Kingdom orchestration">
  <div className="section-heading"><div><h2>Kingdom at work</h2><p className="muted">What is running, who is doing it, and what needs attention.</p></div><span className="sync-note">{updated ? `Updated ${updated.toLocaleTimeString()}` : 'Connecting…'}</span></div>
  {(error || actionError) && <p role="alert" className="notice error">{actionError || error} Last visible data may be out of date.</p>}
  <div className="orchestration-counts">
   <div><strong>{data ? data.counts.knights : '—'}</strong><span>Knight computers</span><small>This controller + {data?.counts.paired_knights ?? '—'} paired</small></div>
   <div><strong>{data ? data.counts.local_apprentices : '—'}</strong><span>Local Apprentices</span><small>Software workers on this Kingdom</small></div>
   <div><strong>{data ? running.length : '—'}</strong><span>Requests running</span><small>{data?.background.active_request_ids.length ?? 0} in the background slot</small></div>
  </div>
  <ol className="orchestration-flow" aria-label="Task completion flow">{['Request','Plan & route','Knight → Apprentice','Tools & tests','Review → result'].map(step=><li key={step}>{step}</li>)}</ol>
  <p className="muted">Work continues when this browser closes while the Kingdom server stays running. A completed response does not prove a tested repair.</p>
  <div className="orchestration-filters" role="group" aria-label="Filter work">{[['attention','Needs attention'],['done','Responses done'],['all','All work']].map(([id,title])=><button key={id} aria-pressed={filter===id} onClick={()=>setFilter(id)}>{title}</button>)}</div>
  {!data ? <p>Loading recorded work…</p> : !visible.length ? <p>No requests in this view. Queued work is not running work.</p> : <div className="orchestration-jobs">{visible.map(job=><article key={job.id} className="orchestration-job">
   <div className="job-heading"><strong>{job.project || 'Unscoped project'}</strong><span className="status-chip">{label(job.display_status || job.status)}</span></div>
   <p>{job.objective}</p>
   <dl className="job-facts"><div><dt>Knight / computer</dt><dd>{job.computer || 'Not recorded'}</dd></div><div><dt>Apprentice / executor</dt><dd>{job.assigned_workers.join(', ') || 'Not assigned yet'}</dd></div><div><dt>Model</dt><dd>{job.model || label(job.model_profile)}</dd></div><div><dt>Execution evidence</dt><dd>{job.verified_tools} verified tools / {job.tool_count} requested</dd></div></dl>
   {job.reason && <p className="job-blocker"><strong>Needs attention:</strong> {job.reason}</p>}
   {job.completion_scope && <p className="muted">{job.completion_scope}</p>}
   {['queued','ready'].includes(job.status) && <button disabled={!!busy || !!data.background.active_request_ids.length} onClick={()=>start(job.id)}>{busy===job.id?'Starting…':'Start bounded background work'}</button>}
   <details><summary>Request details</summary><p>Request {job.id} · {label(job.status)}. Permissions and review gates remain in force. Server interruptions require checkpoint review.</p></details>
  </article>)}</div>}
 </section>
}

import React,{useState} from 'react'
import useLiveData from '../hooks/useLiveData'
import {eventInfo} from './common/userStatus'
import {taskChangeReport,safeRecordedTime} from './common/taskVisibility'

function OpenTaskInsights({task}) {
 const feed=useLiveData(`/tasks/${encodeURIComponent(task.id)}/timeline`,5000)
 const report=taskChangeReport(task)
 const events=Array.isArray(feed.data?.events)?feed.data.events:null
 return <div className="task-insights-panel">
  <section aria-label="Task event timeline">
   <div className="section-heading"><h4>Recorded timeline</h4><button type="button" onClick={feed.refresh}>Refresh timeline</button></div>
   <p className="muted">Only persisted events linked to this task are shown; missing events are not invented. This is not a live recording of the worker.</p>
   {feed.error && <p role="alert">Timeline could not refresh. The events shown may be incomplete or old.</p>}
   {!events ? <p role="status">Loading recorded events…</p> : events.length===0
    ? <p>No task-linked events have been retained for this task.</p>
    : <ol className="task-timeline">{events.map((event,index)=>{
      const info=eventInfo(event.event_type)
      return <li key={event.event_id||index}><strong>{info.title}</strong><time>{safeRecordedTime(event.timestamp)}</time><p>{info.explanation}</p></li>
     })}</ol>}
   {feed.data?.truncated && <p className="muted">Older events exist; this view shows only the newest recorded events.</p>}

  </section>
  <section aria-label="What changed report">
   <h4>What changed? Evidence report</h4>
   {report.lines.length ? <ul>{report.lines.map((line,index)=>
      <li key={index}><strong>{line.label}:</strong> {line.detail}</li>
   )}</ul> : <p>No verified file or artifact change is recorded for this task.</p>}
   <p className="muted">{report.notice}</p>
   {!report.finished && <p className="muted">This task has not reached a recorded success state. Partial receipts do not mean the requested outcome is finished.</p>}
  </section>
 </div>
}
export default function TaskInsights({task}){
 const [open,setOpen]=useState(false)
 if(!task?.id)return null
 return <details className="task-insights" onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary>Timeline and what changed</summary>
  {open && <OpenTaskInsights task={task}/>}
 </details>
}

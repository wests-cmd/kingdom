import React,{useEffect,useState} from 'react'
import useLiveData from '../hooks/useLiveData'
import {activityStages,formatWait} from './common/agentActivity'
import './AgentActivity.css'

export default function AgentActivity({jobId}) {
 const {data,error,updated,refresh}=useLiveData(`/agent-sessions/${encodeURIComponent(jobId)}/activity`,4000)
 const [now,setNow]=useState(Date.now())
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer)},[])
 const activity=data?.id===jobId?data:null
 const wait=activity?.model_wait_seconds+(updated?Math.max(0,Math.floor((now-updated.getTime())/1000)):0)
 return <section className="panel agent-activity" aria-label="Job activity">
  <header><div><p className="agent-activity-kicker">Actual work and evidence</p><h2>{activity?.status_label||'Loading job activity'}</h2></div><button onClick={refresh}>Refresh activity</button></header>
  {error&&<p role="alert">Activity could not be refreshed. Any information below is the last received snapshot, not confirmation that work is still running.</p>}
  {activity&&<>
   <ol className="agent-activity-stages" aria-label="Execution stages">{activityStages(activity).map(stage=><li key={stage.label}><strong>{stage.label}</strong><span>{stage.state}</span></li>)}</ol>
   <dl className="agent-activity-facts">
    <div><dt>Model connection requested</dt><dd>{activity.model_connection}</dd></div>
    <div><dt>Model that responded</dt><dd>{activity.selected_model||'No model response received yet'}</dd></div>
    <div><dt>Tools run on this computer</dt><dd>{activity.tool_host} · {activity.tool_platform}</dd></div>
    <div><dt>Workspace on that computer</dt><dd>{activity.workspace}</dd></div>
    <div><dt>Model turns used</dt><dd>{activity.turns} / {activity.max_turns}</dd></div>
    {activity.status==='thinking'&&<div><dt>Waiting for this model response</dt><dd>{formatWait(wait)}</dd></div>}
   </dl>
   <p><strong>Evidence:</strong> {activity.evidence_summary}</p><p>Existing source files read: {activity.source_reads} · Files written: {activity.file_writes} · Independent tests: not verified</p>
   {activity.attention&&<p className="agent-activity-notice">{activity.attention}</p>}
   {activity.blocker&&<p role="alert" className="agent-activity-blocker"><strong>Blocked:</strong> {activity.blocker}</p>}
   <p className="agent-activity-next"><strong>Next:</strong> {activity.next_action}</p>
   {activity.operations.length>0&&<ul aria-label="Current operations">{activity.operations.map(operation=><li key={operation.task_id}><strong>{operation.tool.replaceAll('_',' ')}</strong> · {operation.status.replaceAll('_',' ')}{operation.worker?` · ${operation.worker}`:''}<br/><small>Task {operation.task_id}</small></li>)}</ul>}
   <details><summary>Execution details and retained events</summary><p>Job {activity.id} · last state change {activity.updated_at?new Date(activity.updated_at*1000).toLocaleString():'unknown'}</p><p>Required execution checks: {activity.acceptance_checks.join(', ')||'None set'}. These checks do not prove independent tests passed.</p>{activity.error_code&&<p>Reason: {activity.error_code}</p>}<ol>{activity.events.map((event,index)=><li key={index}>{new Date(event.at*1000).toLocaleTimeString()} · {event.kind.replaceAll('_',' ')}{event.tool?` · ${event.tool}`:''}{event.task_id?` · task ${event.task_id}`:''}</li>)}</ol></details>
  </>}
 </section>
}

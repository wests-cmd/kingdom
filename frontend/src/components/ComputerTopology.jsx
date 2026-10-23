import React from 'react'
import useLiveData from '../hooks/useLiveData'
import CoordinationGraph from './CoordinationGraph'
import {apprenticeLabel} from './common/presentation'
import {jobStatus,peerVisibility,serviceScope,serviceStatus} from './common/fleetVisibility'

export default function ComputerTopology({hierarchy,advanced=false}){
 const {data:observed}=useLiveData('/service-nodes/discovery',30000)
 const {data:activity}=useLiveData('/orchestration/activity',10000)
 if(!hierarchy)return <p>Loading the computers in this Kingdom…</p>
 const local={id:'local',name:hierarchy.commander?.computer||'This computer',state:'This Knight',apprentices:hierarchy.apprentices||[],services:observed,activity}
 const peers=(hierarchy.knights||[]).map(node=>{
  const id=node.node_id||node.id
  const report=hierarchy.inventory?.reports?.find(item=>item.kingdom_id===id)
  return {id,name:node.hostname||id,state:node.node_state||'Not reported',...peerVisibility(node,report),
   apprentices:(hierarchy.inventory?.remote_apprentices||[]).filter(item=>item.kingdom_id===id)}
 })
 const computers=[local,...peers],shown=computers.slice(0,9)
 const point=index=>index===0?{x:320,y:40}:{x:80+((index-1)%4)*160,y:130+Math.floor((index-1)/4)*90}
 return <section className="panel cluster-topology"><h2>One Kingdom · {computers.length} {computers.length===1?'Knight':'Knights'}</h2>
 <p>Each computer is a Knight. Open one to see its reported work, Apprentices and running or startup-enabled services. Private prompts and conversations are not shared here.</p>
 <svg viewBox="0 0 640 270" role="img" aria-label={`Logical collaboration map of ${computers.length} computers. Lines show pairing, not physical cables.`}>
 {shown.slice(1).map((computer,index)=>{const p=point(index+1);return <line key={computer.id} x1="320" y1="55" x2={p.x} y2={p.y} stroke="currentColor" strokeWidth="2" strokeDasharray={computer.current?undefined:'5 5'}/>})}
 {shown.map((computer,index)=>{const p=point(index);return <g key={computer.id}><rect x={p.x-43} y={p.y-19} width="86" height="38" rx="10" fill="var(--surface-dark)" stroke="var(--accent-readable)"/><text x={p.x} y={p.y+5} textAnchor="middle" fill="var(--text-main)">Knight {index+1}</text></g>})}
 </svg>
 <p className="muted">Lines show approved collaboration, not Ethernet or Wi-Fi wiring. {computers.length>shown.length?`The overview shows ${shown.length}; all computers are listed below.`:''} A missing report is unknown, not zero workers.</p>
 <div className="topology-computers">{computers.map((computer,index)=><details key={computer.id} className="card"><summary>🖥 Knight {index+1}: {computer.name} · {computer.state}</summary>
 <h3>Apprentices</h3>{computer.id!=='local'&&!computer.current?<p>Fresh Apprentice information is unavailable.</p>:computer.apprentices.length?<ul>{computer.apprentices.map(agent=><li key={agent.id}><strong>{apprenticeLabel(agent)}</strong> · {agent.status||'Not reported'}</li>)}</ul>:<p>No Apprentices reported.</p>}
  <details><summary>Reported work {computer.activity?.state==='observed'?`(${computer.activity.jobs.length})`:''}</summary>
  {computer.activity?.state==='observed'?computer.activity.jobs.length?<ul>{computer.activity.jobs.map(job=><li key={`${job.kind}/${job.id}`}><strong>{jobStatus(job.status)}</strong> · {job.kind} {job.id.slice(0,8)}{job.tool&&<span> · {job.tool}</span>}{job.model&&<span> · model {job.model}</span>}{job.worker&&<span> · worker {job.worker}</span>}{advanced&&job.updated_at!=null&&<span> · reported change {new Date(job.updated_at*1000).toLocaleString()}</span>}</li>)}</ul>:<p>No work records reported.</p>:<p>Work information is {computer.reportState||'not available'}. This is unknown, not zero work.</p>}
  {computer.activity?.truncated&&<p>Only the latest 20 work records are shared.</p>}<p className="muted">These are reported states, not independent acceptance of an outcome. Source clocks can differ; freshness uses receipt time. Completed model text does not prove a code change passed its checks.</p></details>
  <details><summary>Running and startup services {computer.services?.state==='observed'?`(${computer.services.services.length})`:''}</summary>{computer.services?.state==='observed'?<ul>{computer.services.services.map(item=><li key={item.id}>{item.name} · {serviceStatus(item)}{advanced?` · ${item.id}`:''}</li>)}</ul>:<p>Observation is {computer.services?.state||'not available'} on this computer.</p>}
  <p>{serviceScope(computer.services)}</p>{computer.services?.startup_state!=='observed'&&<p>Startup information is not available. Running does not mean startup is enabled.</p>}{computer.services?.truncated&&<p>Service list limited to 128 records.</p>}<p className="muted">Detection does not grant control or inventory every program. Starting, stopping or updating requires a separate reviewed management connection.</p></details>
  {advanced&&<p className="muted">Identity: {computer.id} · {computer.id==='local'?'local observation':'signed peer inventory; execution is verified separately'}</p>}
 </details>)}</div>{!!hierarchy.archived_knights?.length&&<details><summary>Previously paired computers</summary>{hierarchy.archived_knights.map(node=><p key={node.node_id}>🖥 {node.hostname||node.node_id} · {node.node_state||'Not reported'} · current work and services unavailable</p>)}</details>}<CoordinationGraph graph={hierarchy.topology}/></section>
}

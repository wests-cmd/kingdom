import React from 'react'
import useLiveData from '../hooks/useLiveData'
import CoordinationGraph from './CoordinationGraph'
import SwarmControls from './SwarmControls'
import {apprenticeLabel} from './common/presentation'
import {jobStatus,peerVisibility,serviceScope,serviceStatus} from './common/fleetVisibility'
import {computerName} from './common/computerName'
import SwarmGroupMap from './SwarmGroupMap'
import {swarmCount} from './common/swarmGroups'

export default function ComputerTopology({hierarchy,advanced=false,onRefresh}){
 const {data:observed}=useLiveData('/service-nodes/discovery',30000)
 const {data:activity}=useLiveData('/orchestration/activity',10000)
 if(!hierarchy)return <p>Loading the computers in this Kingdom…</p>
 const local={id:'local',name:computerName(hierarchy.commander?.username,hierarchy.commander?.display_computer||hierarchy.commander?.computer,'local'),state:'This Knight',apprentices:hierarchy.apprentices||[],services:observed,activity}
 const peers=(hierarchy.knights||[]).map(node=>{
  const id=node.node_id||node.id
  const report=hierarchy.inventory?.reports?.find(item=>item.kingdom_id===id)
  return {id,name:computerName(node.display_username,node.display_computer||node.hostname,id),state:node.node_state||'Not reported',...peerVisibility(node,report),
   apprentices:(hierarchy.inventory?.remote_apprentices||[]).filter(item=>item.kingdom_id===id)}
 })
 const computers=[local,...peers]
 const online=computers.filter(c=>c.id==='local'||c.current).length
 return <section className="panel cluster-topology"><h2>{swarmCount(computers)}</h2><p>{online} online · {computers.length-online} disconnected or awaiting a fresh report</p>
 <p>Each computer is a Knight. Open one to see its reported work, Apprentices and running or startup-enabled services. Private prompts and conversations are not shared here.</p>
 <p className="muted">Paired Knights stay members when offline. A stale heartbeat means availability is unknown; it does not expire pairing or require another invitation. A verified returning Knight can reconnect with its existing permissions.</p>
 <SwarmGroupMap computers={computers} hierarchy={hierarchy} onRefresh={onRefresh}/>
 <details><summary>All Knight reports</summary><div className="topology-computers">{computers.map(computer=><details key={computer.id} className="card"><summary>🖥 {computer.name} · {computer.state}</summary>
 <h3>Apprentices</h3>{computer.id!=='local'&&!computer.current?<p>Fresh Apprentice information is unavailable.</p>:computer.apprentices.length?<ul>{computer.apprentices.map(agent=><li key={agent.id}><strong>{apprenticeLabel(agent)}</strong> · {agent.status||'Not reported'}</li>)}</ul>:<p>No Apprentices reported.</p>}
  <details><summary>Reported work {computer.activity?.state==='observed'?`(${computer.activity.jobs.length})`:''}</summary>
  {computer.activity?.state==='observed'?computer.activity.jobs.length?<ul>{computer.activity.jobs.map(job=><li key={`${job.kind}/${job.id}`}><strong>{jobStatus(job.status)}</strong> · {job.kind} {job.id.slice(0,8)}{job.tool&&<span> · {job.tool}</span>}{job.model&&<span> · model {job.model}</span>}{job.worker&&<span> · worker {job.worker}</span>}{advanced&&job.updated_at!=null&&<span> · reported change {new Date(job.updated_at*1000).toLocaleString()}</span>}</li>)}</ul>:<p>No work records reported.</p>:<p>Work information is {computer.reportState||'not available'}. This is unknown, not zero work.</p>}
  {computer.activity?.truncated&&<p>Only the latest 20 work records are shared.</p>}<p className="muted">These are reported states, not independent acceptance of an outcome. Source clocks can differ; freshness uses receipt time. Completed model text does not prove a code change passed its checks.</p></details>
  <details><summary>Running and startup services {computer.services?.state==='observed'?`(${computer.services.services.length})`:''}</summary>{computer.services?.state==='observed'?<ul>{computer.services.services.map(item=><li key={item.id}>{item.name} · {serviceStatus(item)}{advanced?` · ${item.id}`:''}</li>)}</ul>:<p>Observation is {computer.services?.state||'not available'} on this computer.</p>}
  <p>{serviceScope(computer.services)}</p>{computer.services?.startup_state!=='observed'&&<p>Startup information is not available. Running does not mean startup is enabled.</p>}{computer.services?.truncated&&<p>Service list limited to 128 records.</p>}<p className="muted">Detection does not grant control or inventory every program. Starting, stopping or updating requires a separate reviewed management connection.</p></details>
  {advanced&&<p className="muted">Identity: {computer.id} · {computer.id==='local'?'local observation':'signed peer inventory; execution is verified separately'}</p>}
 </details>)}</div></details>{!!hierarchy.archived_knights?.length&&<details><summary>Archived Knights · {hierarchy.archived_knights.length}</summary><p>Offline Knights are hidden after {hierarchy.visibility?.offline_hours||168} hours. Pairing is retained; verified returning Knights reappear automatically.</p>{hierarchy.archived_knights.map(node=><p key={node.node_id}>🖥 {computerName(node.display_username,node.display_computer||node.hostname,node.node_id)} · {node.node_state||'Not reported'} · current work and services unavailable</p>)}</details>}<details><summary>Permissions and task priorities</summary><SwarmControls hierarchy={hierarchy}/></details><details><summary>Apprentice reporting lines</summary><CoordinationGraph graph={hierarchy.topology}/></details></section>
}

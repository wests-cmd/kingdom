import React from 'react'
import useLiveData from '../hooks/useLiveData'

export default function ComputerTopology({hierarchy,advanced=false}){
 const {data:observed}=useLiveData('/service-nodes/discovery',30000)
 if(!hierarchy)return <p>Loading the computers in this Kingdom…</p>
 const local={id:'local',name:hierarchy.commander?.computer||'This computer',state:'This Knight',apprentices:hierarchy.apprentices||[],services:observed}
 const peers=(hierarchy.knights||[]).map(node=>{
  const id=node.node_id||node.id
  const report=hierarchy.inventory?.reports?.find(item=>item.kingdom_id===id)
  return {id,name:node.hostname||id,state:node.node_state||'Not reported',current:report?.state==='current',
   apprentices:(hierarchy.inventory?.remote_apprentices||[]).filter(item=>item.kingdom_id===id),services:report?.state==='current'?report.services:null}
 })
 const computers=[local,...peers],shown=computers.slice(0,9)
 const point=index=>index===0?{x:320,y:40}:{x:80+((index-1)%4)*160,y:130+Math.floor((index-1)/4)*90}
 return <section className="panel cluster-topology"><h2>One Kingdom · {computers.length} {computers.length===1?'Knight':'Knights'}</h2>
 <p>Each computer is a Knight. Open a computer below to see its Apprentices and observed services.</p>
 <svg viewBox="0 0 640 270" role="img" aria-label={`Logical collaboration map of ${computers.length} computers. Lines show pairing, not physical cables.`}>
 {shown.slice(1).map((computer,index)=>{const p=point(index+1);return <line key={computer.id} x1="320" y1="55" x2={p.x} y2={p.y} stroke="currentColor" strokeWidth="2" strokeDasharray={computer.current?undefined:'5 5'}/>})}
 {shown.map((computer,index)=>{const p=point(index);return <g key={computer.id}><rect x={p.x-43} y={p.y-19} width="86" height="38" rx="10" fill="var(--surface-dark)" stroke="var(--accent-readable)"/><text x={p.x} y={p.y+5} textAnchor="middle" fill="var(--text-main)">Knight {index+1}</text></g>})}
 </svg>
 <p className="muted">Lines show approved collaboration, not Ethernet or Wi-Fi wiring. {computers.length>shown.length?`The overview shows ${shown.length}; all computers are listed below.`:''} A missing report is unknown, not zero workers.</p>
 <div className="topology-computers">{computers.map((computer,index)=><details key={computer.id} className="card"><summary>🖥 Knight {index+1}: {computer.name} · {computer.state}</summary>
  <h3>Knight Apprentices</h3>{computer.id!=='local'&&!computer.current?<p>Fresh Apprentice information is unavailable.</p>:computer.apprentices.length?<ul>{computer.apprentices.map(agent=><li key={agent.id}><strong>{agent.display_name||agent.id}</strong> · {agent.role} · {agent.status||'Not reported'}</li>)}</ul>:<p>No Apprentices reported.</p>}
  <details><summary>Observed running services {computer.services?.state==='observed'?`(${computer.services.services.length})`:''}</summary>{computer.services?.state==='observed'?<ul>{computer.services.services.map(item=><li key={item.id}>{item.name}{advanced?` · ${item.id}`:''}</li>)}</ul>:<p>Observation is {computer.services?.state||'not available'} on this computer.</p>}<p className="muted">Detection does not grant control. Starting, stopping or updating a service requires its reviewed management connection.</p></details>
  {advanced&&<p className="muted">Identity: {computer.id} · {computer.id==='local'?'local observation':'signed peer inventory; execution is verified separately'}</p>}
 </details>)}</div></section>
}

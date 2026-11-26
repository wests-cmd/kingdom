import React from 'react'
import useLiveData from '../hooks/useLiveData'

const labels={request:'Conversation request',mission:'Mission',agent:'Agent job',task:'Task'}
const categories={queued:'Ready / queued',active:'Active',waiting:'Waiting',attention:'Needs attention',recorded_finished:'Recorded finished',cancelled:'Cancelled',unknown:'Unknown'}

function WorkRecord({item}){
 return <li><strong>{labels[item.kind]||'Work record'}</strong> · {item.status.replaceAll('_',' ')}{item.route?' · '+item.route:''}
 <small className="muted"> · {item.id}</small>
 {item.evidence==='retained_controller_receipt'&&<p className="muted">Retained controller receipt; inspect the original evidence to confirm its scope.</p>}
 {item.evidence==='recorded_only'&&<p className="muted">Recorded completion is not independent proof of the requested outcome.</p>}
 {item.unresolved_links>0&&<p role="status">Linked records unavailable or ambiguous ({item.unresolved_links}). Review the original work.</p>}
 {item.children?.length>0&&<ul>{item.children.map(child=><WorkRecord key={child.kind+':'+child.id} item={child}/>)}</ul>}
 </li>
}

export default function UnifiedWorkOverview({onNavigate}){
 const {data,error,updated,refresh}=useLiveData('/work/overview',10000)
 const current=data?.schema==='kingdom.work-projection.v1'&&!error
 return <section className="panel" aria-label="Unified work overview">
 <div className="section-heading"><div><h2>Unified work overview</h2><p className="muted">Conversation requests, missions, agent jobs and tasks, with linked work shown once in this recent snapshot.</p></div><button type="button" onClick={refresh}>Refresh work</button></div>
 {!current?<p role="status">{error?'Work snapshot could not refresh. No current state is confirmed.':'Loading saved work…'}</p>:<>
 <p className="muted">{updated?'Last checked '+updated.toLocaleTimeString():'Saved snapshot'} · up to 100 recent records per source.</p>
 {!data.complete_snapshot&&<p role="status">Partial inventory. Counts are not installation-wide totals; older or invalid records may be absent.</p>}
 <div className="home-summary-grid">{Object.entries(categories).map(([key,label])=><div key={key} className="card"><div className="card-title">{label}</div><div className="card-value">{data.root_counts?.[key]??0}</div><small>Root records in this snapshot</small></div>)}</div>
 {data.items?.length?<details><summary>Inspect linked work ({data.items.length} root records)</summary><ul className="home-task-list">{data.items.map(item=><WorkRecord key={item.kind+':'+item.id} item={item}/>)}</ul></details>:<p>No work records were found in this snapshot.</p>}
 <div className="action-row"><button type="button" onClick={()=>onNavigate?.('Workbench')}>Open conversation</button><button type="button" onClick={()=>onNavigate?.('Tasks')}>Open missions and tasks</button></div>
 </>}
 </section>
}

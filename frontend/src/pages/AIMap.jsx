import React, { useState } from 'react'
import useLiveData from '../hooks/useLiveData'
const views = [{name:'Tasks',path:'/tasks'},{name:'Memory',path:'/memory'},{name:'Workers',path:'/knights'},{name:'Security',path:'/security/audit?limit=50'},{name:'Learning',path:'/learning/activity'}]
export default function AIMap() {
 const [view,setView] = useState(views[0])
 const {data,error,updated} = useLiveData(view.path)
 const rows = Array.isArray(data) ? data : view.name === 'Workers' ? data?.knights || [] : view.name === 'Learning' ? data?.proposals || [] : data?.logs || []
 return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Recorded activity</p><h1>Intelligence records</h1><p>Inspect the records Kingdom actually holds. No generated topology or simulated connections.</p></div><span className="sync-note">{updated ? updated.toLocaleTimeString() : 'Loading…'}</span></div>
  <div className="tab-row">{views.map(item => <button key={item.name} className={view.name === item.name ? 'selected' : ''} onClick={() => setView(item)}>{item.name}</button>)}</div>
  {error && <p role="alert" className="notice error">{error}</p>}
  <section className="panel"><div className="section-heading"><h2>{view.name}</h2><span className="status-chip">{data ? `${rows.length} records` : 'Loading…'}</span></div>{data && !rows.length && <p className="empty-state">No {view.name.toLowerCase()} records are available.</p>}
   {rows.map((row,index) => <div className="record-detail" key={row.id || row.event_id || index}><strong>{view.name} record {index + 1}</strong><span className="muted">{["queued","running","completed","failed","cancelled","ready","working","APPROVED","DENIED","WAITING_APPROVAL"].includes(row.status || row.decision || row.state) ? (row.status || row.decision || row.state) : "Recorded"}</span></div>)}
  </section>
 </div>
}

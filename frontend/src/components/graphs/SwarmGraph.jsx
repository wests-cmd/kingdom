import React from 'react'
import useLiveData from '../../hooks/useLiveData'
export default function SwarmGraph() {
 const {data, error, updated} = useLiveData('/knights')
 const nodes = data?.knights || (Array.isArray(data) ? data : [])
 return <section className="panel live-workers"><div className="section-heading"><h3>Worker activity</h3><span className="sync-note">{updated ? updated.toLocaleTimeString() : 'Loading…'}</span></div>{error && <p role="alert" className="notice error">{error}</p>}
  {data && !nodes.length && <p className="empty-state">No workers are registered.</p>}
  <div className="worker-rows">{nodes.map(node => <article className="worker-row" key={node.id}><span className={`state-dot ${node.health === 'healthy' ? 'healthy' : ''}`} /><div className="worker-identity"><strong>{node.display_name}</strong><small>{node.role} · {node.is_local ? 'This Kingdom' : 'Remote Knight'}</small></div><span className="status-chip">{node.status}</span><p className="worker-activity">{node.activity || 'Status unavailable'}{node.current_task ? ` · Task ${node.current_task}` : ''}</p></article>)}</div>
 </section>
}

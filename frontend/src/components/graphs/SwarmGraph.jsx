import React from 'react'
import useLiveData from '../../hooks/useLiveData'
export default function SwarmGraph() {
 const {data, error, updated} = useLiveData('/knights')
 const nodes = data?.knights || (Array.isArray(data) ? data : [])
 return <section className="panel live-workers"><div className="section-heading"><h3>Worker activity</h3><span className="sync-note">{updated ? updated.toLocaleTimeString() : 'Loading…'}</span></div>{error && <p role="alert" className="notice error">{error}</p>}
  {data && !nodes.length && <p className="empty-state">No workers are registered.</p>}
  <div className="worker-rows">{nodes.map(node => <div className="worker-row" key={node.id}><span className={`state-dot ${node.health === 'healthy' ? 'healthy' : ''}`} /><strong>{node.id}</strong><span>{node.role}</span><span>{node.is_local ? 'Local' : 'Remote'}</span><span className="status-chip">{node.status}</span><small>{node.current_task || 'No active task'}</small></div>)}</div>
 </section>
}

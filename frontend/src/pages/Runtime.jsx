import React, { useState } from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
const modes = [{id:'persistent',title:'Persistent',description:'Check the queue every 100 ms.'},{id:'burst',title:'Burst',description:'Check the queue every 20 ms while the runtime is active.'},{id:'adaptive',title:'Adaptive',description:'Check every 100 ms with queued work, or 500 ms when idle.'}]
export default function Runtime() {
 const {data, error, refresh} = useLiveData('/status', 3000)
 const [busy,setBusy] = useState(false)
 const [message,setMessage] = useState('')
 const change = async (path, method='post', body={}) => {setBusy(true);setMessage('');try {await api[method](path,body);await refresh();setMessage('Runtime updated.')} catch(e){setMessage(e.response?.data?.detail || 'Runtime change failed.')} finally {setBusy(false)}}
 return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Execution</p><h1>Runtime</h1><p>Start or stop task processing and choose the queue cadence.</p></div></div>
  {error && <p role="alert" className="notice error">{error}</p>}
  <div className="grid-cards"><div className="card"><div className="card-title">Engine</div><div className="card-value">{data ? data.running ? 'Running' : 'Stopped' : 'Loading…'}</div></div><div className="card"><div className="card-title">Mode</div><div className="card-value">{data?.mode || 'Loading…'}</div></div><div className="card"><div className="card-title">Version</div><div className="card-value">{data?.version || 'Loading…'}</div></div><div className="card"><div className="card-title">Autonomy</div><div className="card-value">{data ? `L${data.autonomy_level}` : 'Loading…'}</div></div></div>
  <div className="action-row"><button className="primary-red" onClick={() => change('/start')} disabled={!data || busy || data.running || !!error}>Start Runtime</button><button onClick={() => change('/stop')} disabled={!data || busy || !data.running || !!error}>Stop Runtime</button>{message && <span role="status">{message}</span>}</div>
  <section className="panel"><h2>Queue processing mode</h2><p className="muted">Modes change polling speed. They do not grant authority or enable privacy, sandboxing, or a calendar schedule.</p><div className="mode-options">{modes.map(mode => <button key={mode.id} className={`mode-option ${data?.mode === mode.id ? 'selected' : ''}`} onClick={() => change('/mode','put',{mode:mode.id})} disabled={!data || busy || !!error || data.mode === mode.id}><strong>{mode.title}</strong><small>{mode.description}</small><span>{data?.mode === mode.id ? 'Active' : 'Use this mode'}</span></button>)}</div></section>
 </div>
}

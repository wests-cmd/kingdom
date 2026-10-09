import React, { useState, useEffect } from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import ApprovalsView from '../components/security/ApprovalsView'
import ComputerPermissions from '../components/ComputerPermissions'
export default function Governance() {
 const {data, error, refresh, updated} = useLiveData('/runtime/policy')
 const [selected, setSelected] = useState(null)
 const [busy, setBusy] = useState(false)
 const [message, setMessage] = useState('')
 const [saveError, setSaveError] = useState('')
 useEffect(() => {if (selected === null && data) setSelected(data.level)}, [data, selected])
 const apply = async event => {event.preventDefault();setBusy(true);setMessage('');setSaveError('')
  try {const result = await api.put('/runtime/policy', {level: selected});setMessage(`Policy saved: ${result.data.levels.find(item => item.level === result.data.level).name}.`); await refresh()}
  catch (e) {setSaveError(e.response?.data?.detail || 'Policy could not be saved.')} finally {setBusy(false)}
 }
 return <div className="page-stack">
  <div className="page-heading"><div><p className="eyebrow">Human authority</p><h1>Governance</h1><p>Choose what Kingdom may execute. Review individual requests below.</p></div><span className="sync-note">{updated ? `Updated ${updated.toLocaleTimeString()}` : 'Connecting…'}</span></div>
  {(error || saveError) && <p role="alert" className="notice error">{error || saveError}</p>}
  <section className="panel"><div className="section-heading"><h2>Autonomy policy</h2><span className="status-chip">{data ? `Active: L${data.level}` : 'Loading…'}</span></div>
   <p className="muted">Changes apply to queued and future tasks, not a task already executing. Capability grants and high-risk approvals remain mandatory at every level.</p>
   {data && <form onSubmit={apply}><fieldset className="policy-options" disabled={busy || !!error}><legend className="sr-only">Autonomy level</legend>{data.levels.map(level => <label className={`policy-option ${selected === level.level ? 'selected' : ''}`} key={level.level}>
    <input type="radio" name="autonomy" value={level.level} checked={selected === level.level} onChange={() => {setSelected(level.level);setMessage('')}} />
    <span className="policy-number">L{level.level}</span><span><strong>{level.name}</strong><small>{level.description}</small></span>{data.level === level.level && <span className="active-note">Active</span>}
   </label>)}</fieldset><div className="action-row"><button className="primary-red" disabled={busy || selected === data.level || !!error}>{busy ? 'Saving…' : 'Apply policy'}</button>{message && <span role="status">{message}</span>}</div></form>}
  </section><ComputerPermissions /><ApprovalsView />
 </div>
}

import React, {useEffect, useState} from 'react'
import api from '../api'

export default function Automations() {
  const [items, setItems] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const refresh = async () => {
    try { const {data} = await api.get('/automations'); setItems(data.automations); setError('') }
    catch { setError('Could not read automation status. Existing workers keep their current ownership.') }
    finally { setLoading(false) }
  }
  useEffect(() => {refresh(); const timer = setInterval(refresh, 15000); return () => clearInterval(timer)}, [])
  const approve = async item => {
    try { await api.post(`/automations/${encodeURIComponent(item.id)}/approve`, {revision: item.candidate_revision}); await refresh() }
    catch { setError('Approval failed. Refresh and approve the installed revision again.') }
  }
  return <section><h1>Automations</h1><p>Let Kingdom supervise connected work. The original runner stays available until the replacement passes its checks.</p>
    {loading && <p role="status">Reading connected automations…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && !items.length && <p>No automation adapters are connected to this installation yet.</p>}
    {items.map(item => <article className="panel" key={item.id} style={{marginBottom:24,padding:24}}>
      <h2>{item.name}</h2><p>Owner: <strong>{item.owner === 'kingdom' ? 'Kingdom' : 'Original worker'}</strong> · {item.status.replaceAll('_',' ')} · Autonomy level {item.autonomy_level}</p>
      {item.observed && <><p>{item.observed.schedule}</p><p>{item.observed.completed_skills} completed skills. Outputs: {item.observed.outputs.join(', ')}.</p>
        {item.observed.active_work.map(work => <p key={work.skill}>{work.skill}: {work.mode}, {Math.round(work.seconds / 60)} minutes retained ({work.status}).</p>)}</>}
      <ol>{item.plan.map(step => <li key={step}>{step}</li>)}</ol>
      {item.evidence?.passed && <p>Passed checks: {item.evidence.checks?.join(', ')}.</p>}
      {item.last_success && <p>Last successful check-in: {new Date(item.last_success * 1000).toLocaleString()}.</p>}
      <p>Autonomy level 3 or higher and approval of the exact tested adapter are required for automatic handover. Levels 0–2 pause adopted work.</p>
      {item.last_failure && <p role="status">Last failure: {item.last_failure}. Original ownership restored; at most three checked adoption attempts, with a 30-minute delay.</p>}
      {item.last_failure && item.diagnosis && <p>{item.diagnosis}</p>}
      {item.lease && <p role="status">Work is in flight. No second worker may start.</p>}
      <button disabled={!item.adapter_available || !!item.lease || item.approved_revision === item.candidate_revision} onClick={() => approve(item)}>
        {item.approved_revision === item.candidate_revision ? 'Current adapter approved' : 'Approve this adapter for tested handover'}
      </button>
    </article>)}<button onClick={refresh}>Refresh status</button>
  </section>
}

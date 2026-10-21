import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

const label = value => String(value || 'unknown').replaceAll('_', ' ')

export default function WorkBacklogPanel() {
  const {data, error: readError, refresh} = useLiveData('/work-backlog', 5000)
  const {data: missions} = useLiveData('/missions', 10000)
  const [title, setTitle] = useState(''), [description, setDescription] = useState('')
  const [selected, setSelected] = useState(''), [showAll, setShowAll] = useState(false)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [key, setKey] = useState(() => `owner-${Date.now()}-${Math.random().toString(36).slice(2)}`)
  const perform = async action => {
    setBusy(true); setError('')
    try { await action(); await refresh() }
    catch (e) { setError(e.response?.data?.detail || 'Work list could not be updated. Reload its current state.') }
    finally { setBusy(false) }
  }
  const items = data?.items || []
  const choices = (missions || []).filter(mission =>
    mission.approved_version === mission.version &&
    ['approved', 'running', 'completed'].includes(mission.status) &&
    !mission.plan?.missing_requirements?.length &&
    mission.plan?.steps?.some(step => step.kind === 'function_check'))
  const counts = {
    'In progress': items.filter(item => item.status === 'running').length,
    'Verified complete': items.filter(item => item.status === 'completed').length,
    'Needs a plan': items.filter(item => item.status === 'needs_planning').length,
    'Needs review': items.filter(item => ['review_required', 'failed'].includes(item.status)).length,
  }
  return <section className="panel" style={{minWidth: 0, overflowWrap: 'anywhere'}}>
    <h2>Kingdom work list</h2>
    <p>Kingdom reviews this saved list while its service runs, even with this page closed. Reviewed missions keep their own fixed checks. A proposal or model answer cannot mark work complete.</p>
    {(error || readError) && <p role="alert">{error || 'Could not read the work list.'}</p>}
    {!data ? <p role="status">Reading saved work…</p> : <>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(8rem,1fr))',gap:12}}>
        {Object.entries(counts).map(([name, count]) => <div key={name}><strong>{count}</strong><br/>{name}</div>)}
      </div>
      <p><strong>{data.enabled ? 'Automatic selection enabled' : 'Automatic selection paused'}</strong>. Execution also requires a running runtime, autonomy level 4 or 5 and existing permissions. Planning notes do not execute.</p>
      <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
        <button disabled={busy} onClick={() => perform(() => api.post('/work-backlog/settings', {enabled:!data.enabled, expected_revision:data.revision}))}>{data.enabled ? 'Pause automatic selection' : 'Enable reviewed work'}</button>
        <button disabled={busy} onClick={() => perform(() => api.post('/work-backlog/review'))}>Review current evidence</button>
      </div>
      {!items.length && <p>No work saved yet. Add a note or link a reviewed mission below.</p>}
      {(showAll ? items : items.slice(0, 8)).map(item => <article key={item.id} className="record-detail">
        <h3>{item.title}</h3>
        <p><strong>{label(item.status)}</strong> · priority {item.priority}</p>
        <p>{item.reason}</p>
        {item.next_step && <p>Next: {item.next_step}</p>}
        {['ready','paused'].includes(item.status) && !item.lease && <button disabled={busy} onClick={() => perform(() => api.post(`/work-backlog/items/${encodeURIComponent(item.project)}/${encodeURIComponent(item.id)}/settings`, {enabled:!item.enabled,expected_revision:item.revision}))}>{item.enabled ? 'Pause this item' : 'Enable this reviewed item'}</button>}
        {item.description && <details><summary>Requested outcome</summary><p style={{whiteSpace:'pre-wrap'}}>{item.description}</p></details>}
        <details><summary>Mission and verification receipt</summary>
          <p>Mission: {item.intent?.mission_id || 'No executable mission yet'}{item.intent?.mission_version ? ` · version ${item.intent.mission_version}` : ''}</p>
          <p>Check: {item.intent?.acceptance_step || 'Not selected'}</p>
          {item.evidence ? <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(item.evidence,null,2)}</pre> : <p>No accepted test receipt. This is not verified complete.</p>}
        </details>
        {item.status === 'needs_planning' && !!choices.length && <label>Attach a reviewed mission<select defaultValue="" disabled={busy} onChange={event => {
          const mission = choices.find(choice => choice.id === event.target.value)
          if (!mission) return
          const step = mission.plan.steps.find(check => check.kind === 'function_check')
          perform(() => api.post(`/work-backlog/items/${encodeURIComponent(item.project)}/${encodeURIComponent(item.id)}/mission`, {mission_id:mission.id,mission_version:mission.version,acceptance_step:step.id,expected_revision:item.revision}))
        }}><option value="">Choose a reviewed mission…</option>{choices.map(mission => <option key={mission.id} value={mission.id}>{mission.plan.title} · version {mission.version}</option>)}</select></label>}
      </article>)}
      {items.length > 8 && <button onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer items' : `Show all ${items.length} items`}</button>}
      {!!data.findings?.length && <details><summary>{data.findings.length} evidence-based suggestions for review</summary>
        {data.findings.map(finding => <article key={finding.id}><p>{finding.provenance?.reason}</p><p>{finding.next_step}</p><p>Mission: {finding.provenance?.mission_id} · {label(finding.provenance?.mission_status)}</p></article>)}
      </details>}
    </>}
    <details><summary>Add an outcome to the list</summary>
      <form onSubmit={event => {event.preventDefault(); perform(async () => {
        const mission = choices.find(item => item.id === selected)
        const step = mission?.plan.steps.find(item => item.kind === 'function_check')
        await api.post('/work-backlog/items', {project:'kingdom',idempotency_key:key,title,description,
          ...(mission ? {mission_id:mission.id,mission_version:mission.version,acceptance_step:step.id} : {})})
        setTitle('');setDescription('');setSelected('');setKey(`owner-${Date.now()}-${Math.random().toString(36).slice(2)}`)
      })}}>
        <label>Outcome<input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)}/></label>
        <label>What should be different when it is finished?<textarea maxLength={12000} rows={3} value={description} onChange={e => setDescription(e.target.value)}/></label>
        <label>Reviewed mission (optional)<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Save as a planning note</option>{choices.map(item => <option key={item.id} value={item.id}>{item.plan.title} · version {item.version}</option>)}</select></label>
        <p>New entries start paused. A planning note needs an executable reviewed mission before it can run. Current automatic checks cover a bounded arithmetic function subset, not arbitrary repository builds.</p>
        <button disabled={busy || !title.trim()}>Save outcome</button>
      </form>
    </details>
  </section>
}

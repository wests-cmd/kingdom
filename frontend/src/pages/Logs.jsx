import React, { useState } from 'react'
import useLiveData from '../hooks/useLiveData'
import {eventInfo} from '../components/common/userStatus'

const EVENT_FILTERS = [
  ['task.queued', 'Task added to queue'],
  ['task.waiting_approval', 'Task awaiting approval'],
  ['task.running', 'Task started'],
  ['task.completed', 'Task completed'],
  ['task.failed', 'Task failed'],
  ['task.cancelled', 'Task cancelled'],
  ['governance.approval_required', 'Approval requested'],
  ['runtime.started', 'Runtime started'],
]

function recordedTime(value) {
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : 'Time not reported'
}

export default function Logs() {
  const [filterType, setFilterType] = useState('')
  const {data, error, updated, refresh} = useLiveData(
    filterType ? `/events?event_type=${encodeURIComponent(filterType)}` : '/events', 3000
  )
  const events = Array.isArray(data) ? data : []

  return <section className="panel" aria-label="What Kingdom has recorded">
    <div className="section-heading">
      <div><h2>What Kingdom has recorded</h2>
        <p className="muted">This activity history tells you which changes Kingdom recorded and when. A message or logged event alone does not prove a task's external outcome.</p>
      </div>
      <button type="button" onClick={refresh}>Refresh history</button>
    </div>
    <label>Show events
      <select value={filterType} onChange={e => setFilterType(e.target.value)}
        style={{marginLeft:8,padding:'6px 12px',background:'var(--input-bg)',color:'var(--text-main)',border:'1px solid var(--surface-border)'}}>
        <option value="">All recorded events</option>
        {EVENT_FILTERS.map(([id,title]) => <option key={id} value={id}>{title}</option>)}
      </select>
    </label>
    <p className="muted">{updated ? `Last refreshed ${updated.toLocaleTimeString()}` : 'Waiting for event records…'}</p>
    {error && <p role="alert">Could not update activity history. Previously displayed events may be old; reconnect and try again.</p>}
    <h3>Recorded events ({data ? events.length : '—'})</h3>
    {!data ? <p>Loading activity…</p> : events.length === 0 ?
      <p>{error ? 'No current activity information is available.' : 'No events recorded for this filter.'}</p> :
      <ol style={{listStyle:'none',padding:0,display:'flex',flexDirection:'column',gap:8}}>
        {events.map((event,index) => {
          const info = eventInfo(event?.event_type)
          return <li key={event?.event_id || index} className="card" style={{padding:'12px 16px'}}>
            <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap'}}>
              <strong>{info.title}</strong>
              <time className="muted">{recordedTime(event?.timestamp)}</time>
            </div>
            <p>{info.explanation}</p>
            {event?.task_id && <p className="muted">Related task: {event.task_id}</p>}
            <details><summary>Technical event details</summary>
              <p>Recorded type: {typeof event?.event_type === 'string' ? event.event_type : 'Not reported'}</p>
              <p>Reported by: {typeof event?.source === 'string' ? event.source : 'Not reported'}</p>
              {event?.event_id && <p>Event reference: {event.event_id}</p>}
            </details>
          </li>
        })}
      </ol>}
  </section>
}

import React, { useState, useEffect } from "react"
import api from "../api"
import SwarmGraph from "../components/graphs/SwarmGraph"
import ApprovalsView from "../components/security/ApprovalsView"
import Tasks from "./Tasks"
import useLiveData from "../hooks/useLiveData"
import ComputerIdentity from "../components/ComputerIdentity"
import OrchestrationBoard from '../components/OrchestrationBoard'
import { startPolling } from '../common/polling'
import {plainLanguageOverview} from '../components/common/userStatus'

export default function Dashboard() {
  const {data: hierarchy, error: hierarchyError} = useLiveData("/hierarchy", 10000)
  const [status, setStatus] = useState({})
  const [knights, setKnights] = useState([])
  const [tasks, setTasks] = useState([])
  const [security, setSecurity] = useState({})

  const [connectionState, setConnectionState] = useState("CONNECTING")
  const [lastUpdated, setLastUpdated] = useState(null)
  const [actionError, setActionError] = useState('')

  const fetchDashboardData = () => {
    return Promise.all([
      api.get("/status"),
      api.get("/knights"),
      api.get("/tasks"),
      api.get("/security/status")
    ]).then(([statusRes, knightsRes, tasksRes, secRes]) => {
      setStatus(statusRes.data || {})
      setKnights(knightsRes.data?.knights || knightsRes.data || [])
      setTasks(tasksRes.data || [])
      setSecurity(secRes.data || {})
      setConnectionState("LIVE")
      setLastUpdated(new Date().toLocaleTimeString())
    }).catch(() => {
      setConnectionState("OFFLINE")
    })
  }

  useEffect(() => {
    return startPolling(fetchDashboardData, 3000)
  }, [])

  const changeRuntime = async action => {
    setActionError('')
    try {
      await api.post(action === 'start' ? '/start' : '/stop')
      await fetchDashboardData()
    } catch {
      setActionError('Could not change Runtime. Check the connection and try again.')
    }
  }
  const overview = plainLanguageOverview({
    connection: connectionState, lastUpdated, runtime: status, security, tasks
  })
  const counts = overview.counts
  const isCurrent = connectionState === 'LIVE' && !!lastUpdated

  return (
    <div style={{minWidth:0, overflowWrap:"anywhere"}}>
      <ComputerIdentity data={hierarchy} error={hierarchyError}/>
      <section className="panel" aria-label="Kingdom explained" style={{marginBottom:20}}>
        <div className="section-heading">
          <div>
            <h2>Kingdom right now</h2>
            <p className="muted">The last status received from this Kingdom installation, in plain language.</p>
          </div>
          <button type="button" onClick={fetchDashboardData}>Refresh status</button>
        </div>
        <p role="status"><strong>{overview.headline}</strong></p>
        <p>{overview.explanation}</p>
        <p><strong>What to do next:</strong> {overview.next}</p>
        <div className="grid-cards" aria-label="Recorded task counts" style={{marginTop:12}}>
          <div className="card"><strong>{counts ? counts.queued : '—'}</strong><small>Waiting to start</small></div>
          <div className="card"><strong>{counts ? counts.running : '—'}</strong><small>In progress or assigned</small></div>
          <div className="card"><strong>{counts ? counts.approvals : '—'}</strong><small>Tasks waiting for approval</small></div>
          <div className="card"><strong>{counts ? counts.recovery : '—'}</strong><small>Blocked or need recovery</small></div>
          <div className="card"><strong>{counts ? counts.completed : '—'}</strong><small>Recorded as completed</small></div>
          <div className="card"><strong>{counts ? counts.failed : '—'}</strong><small>Failed</small></div>
        </div>
        {counts?.unknown > 0 && <p className="muted">{counts.unknown} task records have an unrecognized status. Check their details before interpreting them.</p>}
        {overview.stale && <p role="alert">These are last-seen counts, not a live report. No new work or approval status can be confirmed until Kingdom reconnects.</p>}
        <details><summary>What do these numbers mean?</summary><p>Waiting means saved but not started. Assigned means a worker has a lease, not proof of execution. Completed is a recorded task state; inspect the result and verification. A model reply or an online computer alone is not proof that the requested action succeeded.</p></details>
      </section>
      <OrchestrationBoard/>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", padding: "8px 16px", background: "var(--input-bg)", border: "1px solid var(--surface-border)", borderRadius: "6px" }}>
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          Connection to Kingdom: <span style={{ fontWeight: "700" }}>{connectionState === 'LIVE' ? 'Updated' : connectionState === 'OFFLINE' ? 'Cannot refresh' : 'Connecting'}</span>
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          {lastUpdated ? `Last synchronized at ${lastUpdated}` : "Synchronizing state..."}
        </div>
      </div>

      <div className="grid-cards">
        <div className="card">
          <div className="card-title">System Status</div>
          <div className="card-value" style={{ color: status.running ? "var(--accent-green)" : "var(--text-muted)" }}>
            {!lastUpdated ? "Loading…" : !isCurrent ? "Last known (offline)" : status.running ? "ACTIVE" : "STOPPED"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Runtime Mode</div>
          <div className="card-value" style={{ textTransform: "capitalize" }}>
            {status.mode || "Loading…"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Local Apprentices</div>
          <div className="card-value">{hierarchy && !hierarchyError && Array.isArray(hierarchy.apprentices) ? hierarchy.apprentices.length : '—'}</div>
        </div>

        <div className="card">
          <div className="card-title">Not finished (recorded)</div>
          <div className="card-value">{counts ? counts.queued + counts.running + counts.approvals + counts.recovery : '—'}</div>
        </div>

        <div className="card">
          <div className="card-title">Pending Approvals</div>
          <div className="card-value" style={{ color: security.pending_approvals_count > 0 ? "var(--accent-red)" : "var(--text-main)" }}>
            {isCurrent && Number.isInteger(security.pending_approvals_count) ? security.pending_approvals_count : '—'}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: "20px", display: "flex", flexWrap: "wrap", gap: "12px" }}>
        <button className="primary-red" onClick={() => changeRuntime('start')} disabled={!isCurrent || status.running}>Start Runtime</button>
        <button onClick={() => changeRuntime('stop')} disabled={!isCurrent || !status.running}>Stop Runtime</button>
        {actionError && <p role="alert">{actionError}</p>}
      </div>

      <ApprovalsView />

      <div style={{ marginTop: "24px" }}>
        <Tasks />
      </div>

      <div style={{ marginTop: "24px" }}>
        <SwarmGraph />
      </div>
    </div>
  )
}

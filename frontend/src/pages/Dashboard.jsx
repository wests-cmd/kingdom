import React, { useState, useEffect } from "react"
import api from "../api"
import SwarmGraph from "../components/graphs/SwarmGraph"
import ApprovalsView from "../components/security/ApprovalsView"
import Tasks from "./Tasks"

export default function Dashboard() {
  const [status, setStatus] = useState({})
  const [knights, setKnights] = useState([])
  const [tasks, setTasks] = useState([])
  const [security, setSecurity] = useState({})

  const fetchDashboardData = () => {
    api.get("/status").then(r => setStatus(r.data || {})).catch(() => {})
    api.get("/knights").then(r => setKnights(r.data || [])).catch(() => {})
    api.get("/tasks").then(r => setTasks(r.data || [])).catch(() => {})
    api.get("/security/status").then(r => setSecurity(r.data || {})).catch(() => {})
  }

  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleStart = () => api.post("/start").then(fetchDashboardData)
  const handleStop = () => api.post("/stop").then(fetchDashboardData)

  return (
    <div>
      <div className="grid-cards">
        <div className="card">
          <div className="card-title">System Status</div>
          <div className="card-value" style={{ color: status.running ? "var(--accent-green)" : "var(--text-muted)" }}>
            {status.running ? "ACTIVE" : "STOPPED"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Runtime Mode</div>
          <div className="card-value" style={{ textTransform: "capitalize" }}>
            {status.mode || "adaptive"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Online Knights</div>
          <div className="card-value">{knights.length}</div>
        </div>

        <div className="card">
          <div className="card-title">Active Tasks</div>
          <div className="card-value">{tasks.filter(t => t.status === "queued" || t.status === "running").length}</div>
        </div>

        <div className="card">
          <div className="card-title">Pending Approvals</div>
          <div className="card-value" style={{ color: security.pending_approvals > 0 ? "var(--accent-red)" : "var(--text-main)" }}>
            {security.pending_approvals || 0}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: "20px", display: "flex", gap: "12px" }}>
        <button className="primary-red" onClick={handleStart} disabled={status.running}>Start Runtime</button>
        <button onClick={handleStop} disabled={!status.running}>Stop Runtime</button>
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

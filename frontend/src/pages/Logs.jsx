import React, { useState, useEffect } from "react"
import useLiveData from "../hooks/useLiveData"

export default function Logs() {
  const [filterType, setFilterType] = useState("")
  const {data, error} = useLiveData(filterType ? `/events?event_type=${encodeURIComponent(filterType)}` : "/events",3000)
  const events = data || []

  return (
    <div>
      <h2>Operational Event Timeline</h2>
      {error && <p role="alert">{error}</p>}

      <div style={{ margin: "16px 0", display: "flex", gap: "12px", alignItems: "center" }}>
        <label style={{ fontSize: "12px", color: "var(--text-muted)" }}>Filter Event Type:</label>
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          style={{ padding: "6px 12px", background: "#222", color: "#fff", border: "1px solid var(--surface-border)", borderRadius: "4px" }}
        >
          <option value="">All Events</option>
          <option value="task.queued">task.queued</option>
          <option value="task.waiting_approval">task.waiting_approval</option>
          <option value="task.running">task.running</option>
          <option value="task.completed">task.completed</option>
          <option value="task.failed">task.failed</option>
          <option value="task.cancelled">task.cancelled</option>
          <option value="governance.approval_required">governance.approval_required</option>
          <option value="runtime.started">runtime.started</option>
        </select>
      </div>

      <h4>Event Log History ({events.length})</h4>
      {events.length === 0 ? <p style={{ color: "#888" }}>No event history recorded.</p> : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px" }}>
          {events.map(e => (
            <div key={e.event_id} className="card" style={{ padding: "10px 14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                <span style={{ fontWeight: "700", color: e.event_type.startsWith("task.completed") ? "var(--accent-green)" : e.event_type.includes("failed") ? "var(--accent-red)" : "var(--accent-orange)" }}>
                  {e.event_type}
                </span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {new Date(typeof e.timestamp === "number" ? e.timestamp * 1000 : e.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Source: {e.source} {e.task_id ? `| Task ID: ${e.task_id}` : ""}</div>
              <div style={{ fontSize: "12px", marginTop: "4px", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{e.event_type.startsWith("task.") ? "Task state updated." : e.event_type.startsWith("knight.") ? "Worker state updated." : "Kingdom recorded an activity update."}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

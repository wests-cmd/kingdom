import React, { useState, useEffect } from "react"
import api from "../api"

export default function Runtime() {
  const [status, setStatus] = useState({})
  const modes = ["persistent", "burst", "adaptive", "scheduled", "privacy", "sandbox"]

  const fetchStatus = () => {
    api.get("/status").then(r => setStatus(r.data || {})).catch(() => {})
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  return (
    <div>
      <h2>Runtime Observability & Controls</h2>

      <div className="grid-cards" style={{ margin: "16px 0" }}>
        <div className="card">
          <div className="card-title">Engine State</div>
          <div className="card-value" style={{ color: status.running ? "var(--accent-green)" : "var(--text-muted)" }}>
            {status.running ? "RUNNING" : "STOPPED"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Active Mode</div>
          <div className="card-value" style={{ textTransform: "capitalize" }}>
            {status.mode || "adaptive"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Version</div>
          <div className="card-value">{status.version || "40.1"}</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "20px" }}>
        <div className="card-title">Available Runtime Modes</div>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "8px" }}>
          {modes.map(m => (
            <span
              key={m}
              style={{
                padding: "6px 12px",
                borderRadius: "4px",
                background: status.mode === m ? "#221516" : "#222",
                border: status.mode === m ? "1px solid var(--accent-red)" : "1px solid var(--surface-border)",
                color: status.mode === m ? "#f87171" : "var(--text-main)",
                fontSize: "12px",
                textTransform: "capitalize"
              }}
            >
              {m} {status.mode === m ? "(Active)" : ""}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

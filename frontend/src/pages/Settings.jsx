import React, { useState, useEffect } from "react"
import api from "../api"

export default function Settings() {
  const [security, setSecurity] = useState({})
  const [audit, setAudit] = useState([])

  useEffect(() => {
    api.get("/security/status").then(r => setSecurity(r.data || {})).catch(() => {})
    api.get("/security/audit?limit=20").then(r => setAudit(r.data || [])).catch(() => {})
  }, [])

  return (
    <div>
      <h2>Security & Zero-Trust Engine</h2>

      <div className="grid-cards" style={{ margin: "16px 0" }}>
        <div className="card">
          <div className="card-title">Zero Trust Model</div>
          <div className="card-value" style={{ color: "var(--accent-green)" }}>
            {security.zero_trust ? "ENFORCED" : "INACTIVE"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Default Policy</div>
          <div className="card-value" style={{ color: "var(--accent-red)" }}>
            {security.deny_by_default ? "DENY-BY-DEFAULT" : "ALLOW"}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Capabilities Count</div>
          <div className="card-value">{security.capabilities_count || 14}</div>
        </div>
      </div>

      <h4>Security Audit Log ({audit.length})</h4>
      {audit.length === 0 ? <p style={{ color: "#888" }}>No security audit records logged.</p> : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px" }}>
          {audit.map((a, i) => (
            <div key={i} className="card" style={{ padding: "10px 14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: "700", color: a.decision === "authorized" ? "var(--accent-green)" : "var(--accent-red)" }}>
                  {a.decision.toUpperCase()} — {a.operation} ({a.capability})
                </span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {new Date(a.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>Actor: {a.actor} | Node: {a.node}</div>
              <div style={{ fontSize: "12px", marginTop: "2px" }}>Reason: {a.reason}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

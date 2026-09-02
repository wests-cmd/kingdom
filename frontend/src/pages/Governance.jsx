import React from "react"
import ApprovalsView from "../components/security/ApprovalsView"

export default function Governance() {
  const levels = [
    { level: "L0", title: "Observer", desc: "Monitors events, zero execution authority" },
    { level: "L1", title: "Assistant Knight", desc: "Executes read-only operations and safe queries" },
    { level: "L2", title: "Bounded Executor", desc: "Executes pre-approved routines and low-risk file writes" },
    { level: "L3", title: "Workflow Orchestrator", desc: "Coordinates multi-knight workflows within granted scopes" },
    { level: "L4", title: "Subsystem Coordinator", desc: "Manages subsystem resources under human policy oversight" },
    { level: "L5", title: "Commander", desc: "Root administrative authority (Requires explicit human approval)" }
  ]

  return (
    <div>
      <h2>Governance & Authority Hierarchy</h2>

      <div style={{ margin: "16px 0" }}>
        <h4>Autonomy Control Levels</h4>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px", marginTop: "10px" }}>
          {levels.map(l => (
            <div key={l.level} className="card">
              <div style={{ color: "var(--accent-red)", fontWeight: "700" }}>{l.level} — {l.title}</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>{l.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: "24px" }}>
        <ApprovalsView />
      </div>
    </div>
  )
}

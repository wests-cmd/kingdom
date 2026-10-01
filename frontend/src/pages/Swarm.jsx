import React, { useState, useEffect } from "react"
import useLiveData from "../hooks/useLiveData"
import SwarmGraph from "../components/graphs/SwarmGraph"

export default function Swarm() {
  const {data,error} = useLiveData("/knights",4000)
  const knights = data?.knights || (Array.isArray(data) ? data : [])
  const loading = !data
  const [selectedKnight,setSelectedKnight] = useState(null)
  useEffect(() => {setSelectedKnight(previous => knights.find(knight => knight.id === previous?.id) || knights[0] || null)},[data])

  return (
    <div>
      <h2>Workers</h2>
      {error && <p role="alert">{error}</p>}

      <div className="worker-inspector-layout">
        <div>
          <h4>Cluster Nodes ({knights.length})</h4>
          {loading ? <p style={{ color: "#888" }}>Loading node cluster...</p> : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "12px", marginTop: "10px" }}>
              {knights.map(k => (
                <div
                  key={k.id}
                  onClick={() => setSelectedKnight(k)}
                  className="card"
                  style={{
                    cursor: "pointer",
                    border: selectedKnight?.id === k.id ? "1px solid var(--accent-red)" : "1px solid var(--surface-border)",
                    background: selectedKnight?.id === k.id ? "#221516" : "var(--surface-dark)"
                  }}
                >
                  <div style={{ fontWeight: "700", marginBottom: "4px" }}>{k.id}</div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "capitalize" }}>Role: {k.role}</div>
                  <div style={{ fontSize: "12px", marginTop: "6px" }}>
                    State: <span style={{ color: k.status === "idle" ? "var(--accent-green)" : k.status === "offline" ? "var(--accent-red)" : "var(--accent-orange)" }}>{k.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: "24px" }}>
            <SwarmGraph />
          </div>
        </div>

        {/* Node Detail Drawer Panel */}
        <div className="card" style={{ height: "fit-content" }}>
          <div className="card-title">Node Telemetry Inspector</div>
          {selectedKnight ? (
            <div>
              <h3 style={{ fontSize: "16px", marginBottom: "12px" }}>{selectedKnight.id}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
                <div><strong>Role:</strong> {selectedKnight.role}</div>
                <div><strong>Status:</strong> {selectedKnight.status}</div>
                <div><strong>Health:</strong> {selectedKnight.health}</div>
                <div><strong>Execution:</strong> {selectedKnight.is_local ? "Local Process" : "Remote Node"}</div>
                <div><strong>Current Task:</strong> {selectedKnight.current_task || "None (Idle)"}</div>
                <div><strong>Capabilities:</strong></div>
                <ul style={{ paddingLeft: "16px", fontSize: "12px", color: "var(--text-muted)" }}>
                  {(selectedKnight.capabilities || []).map((cap, i) => <li key={i}>{cap}</li>)}
                </ul>
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>Select a node to inspect telemetry.</p>
          )}
        </div>
      </div>
    </div>
  )
}

import React, { useState, useEffect } from "react"
import useLiveData from "../hooks/useLiveData"
import SwarmGraph from "../components/graphs/SwarmGraph"
import ComputerIdentity from "../components/ComputerIdentity"

export default function Swarm() {
  const {data: hierarchy, error: hierarchyError} = useLiveData("/hierarchy",10000)
  const {data,error} = useLiveData("/knights",4000)
  const knights = data?.knights || (Array.isArray(data) ? data : [])
  const loading = !data
  const [selectedKnight,setSelectedKnight] = useState(null)
  useEffect(() => {setSelectedKnight(previous => knights.find(knight => knight.id === previous?.id) || knights[0] || null)},[data])

  return (
    <div style={{minWidth:0,overflowWrap:"anywhere"}}>
      <ComputerIdentity data={hierarchy} error={hierarchyError}/>
      <h2>Knight Apprentices</h2>
      {error && <p role="alert">{error}</p>}

      <div className="worker-inspector-layout">
        <div>
          <h4>Agents on {hierarchy?.commander?.computer || "the controller computer"} ({knights.length})</h4>
          {loading ? <p style={{ color: "var(--text-muted)" }}>Loading software agents…</p> : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 180px), 1fr))", gap: "12px", marginTop: "10px" }}>
              {knights.map(k => (
                <button
                  key={k.id}
                  onClick={() => setSelectedKnight(k)}
                  aria-pressed={selectedKnight?.id === k.id}
                  className="card"
                  style={{
                    cursor: "pointer",
                    textAlign: "left",
                    border: selectedKnight?.id === k.id ? "1px solid var(--accent-red)" : "1px solid var(--surface-border)",
                    background: selectedKnight?.id === k.id ? "#221516" : "var(--surface-dark)"
                  }}
                >
                  <span style={{ display: "block", fontWeight: "700", marginBottom: "4px" }}>{k.display_name}</span>
                  <span style={{ display: "block", fontSize: "12px", color: "var(--text-muted)", textTransform: "capitalize" }}>Role: {k.role}</span>
                  <span style={{ display: "block", fontSize: "12px", marginTop: "6px" }}>
                    State: <span style={{ color: k.status === "idle" ? "var(--accent-green)" : k.status === "offline" ? "var(--accent-red)" : "var(--accent-orange)" }}>{k.status}</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          <div style={{ marginTop: "24px" }}>
            <SwarmGraph />
          </div>
        </div>

        {/* Node Detail Drawer Panel */}
        <div className="card" style={{ height: "fit-content", minWidth:0, overflowWrap:"anywhere" }}>
          <div className="card-title">Worker details</div>
          {selectedKnight ? (
            <div>
              <h3 style={{ fontSize: "16px", marginBottom: "12px" }}>{selectedKnight.display_name}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
                <div><strong>Role:</strong> {selectedKnight.role}</div>
                <div><strong>Status:</strong> {selectedKnight.status}</div>
                <div><strong>Health:</strong> {selectedKnight.health}</div>
                <div><strong>Entity:</strong> Knight Apprentice (software agent)</div>
                <div><strong>Host computer:</strong> {hierarchy?.apprentices?.find(agent => agent.id === selectedKnight.id)?.host || "Not reported"}</div>
                <div><strong>Current Task:</strong> {selectedKnight.activity || "Status unavailable"}</div>
                <div><strong>Current permissions:</strong></div>
                <ul style={{ paddingLeft: "16px", fontSize: "12px", color: "var(--text-muted)" }}>
                  {(selectedKnight.capabilities || []).map((cap, i) => <li key={i}>{({"model.inference":"Model text permission","memory.read":"Read knowledge permission","compute":"Built-in text and syntax analysis","providers.test":"Reviewed provider-test permission"})[cap] || "Unsupported permission"}</li>)}
                </ul>
                <p className="muted">Model text needs a configured provider. Provider tests also need an enabled service.</p>
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>Select an agent to inspect its reported activity.</p>
          )}
        </div>
      </div>
    </div>
  )
}

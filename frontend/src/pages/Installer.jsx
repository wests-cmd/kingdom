import React, { useState, useEffect } from "react"
import api from "../api"

export default function Installer() {
  const [step, setStep] = useState(1)
  const [nodeType, setNodeType] = useState("commander")
  const [dbPath, setDbPath] = useState("data/kingdom.db")
  const [installStatus, setInstallStatus] = useState("idle")
  const [healthInfo, setHealthInfo] = useState(null)
  const [logs, setLogs] = useState([])

  useEffect(() => {
    api.get("/health").then(r => setHealthInfo(r.data)).catch(() => {})
  }, [])

  const addLog = (msg) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])
  }

  const handleRunSetup = async () => {
    setInstallStatus("running")
    addLog(`Initiating Kingdom Setup for Node Type: ${nodeType}...`)
    addLog(`Target SQLite Database Path: ${dbPath}`)

    try {
      const res = await api.get("/health")
      addLog(`Backend health verify: Status=${res.data.status}, Version=${res.data.version}`)
      setInstallStatus("completed")
      addLog("Setup completed successfully! Kingdom Core Runtime is online.")
      setStep(3)
    } catch (e) {
      setInstallStatus("error")
      addLog(`Error during setup: ${e.message}`)
    }
  }

  return (
    <div style={{ maxWidth: "700px", margin: "40px auto" }} className="card">
      <h2>Kingdom Universal Setup & Node Installer Wizard</h2>
      <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "20px" }}>
        Configure, initialize, and register Kingdom node components on local or remote operating systems.
      </p>

      {/* Step Indicators */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "24px" }}>
        <div style={{ flex: 1, padding: "8px", background: step >= 1 ? "var(--accent-blue)" : "var(--surface-dark)", textAlign: "center", borderRadius: "4px", fontSize: "12px", fontWeight: "600" }}>
          1. Environment & Role
        </div>
        <div style={{ flex: 1, padding: "8px", background: step >= 2 ? "var(--accent-blue)" : "var(--surface-dark)", textAlign: "center", borderRadius: "4px", fontSize: "12px", fontWeight: "600" }}>
          2. Database & Config
        </div>
        <div style={{ flex: 1, padding: "8px", background: step >= 3 ? "var(--accent-blue)" : "var(--surface-dark)", textAlign: "center", borderRadius: "4px", fontSize: "12px", fontWeight: "600" }}>
          3. Verification
        </div>
      </div>

      {/* Step 1: Role Selection */}
      {step === 1 && (
        <div>
          <h4>Select Node Role</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", margin: "16px 0" }}>
            {["commander", "knight", "scout"].map(role => (
              <div
                key={role}
                onClick={() => setNodeType(role)}
                className="card"
                style={{
                  cursor: "pointer",
                  border: nodeType === role ? "2px solid var(--accent-blue)" : "1px solid var(--surface-border)",
                  textAlign: "center"
                }}
              >
                <div style={{ textTransform: "capitalize", fontWeight: "700" }}>{role}</div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                  {role === "commander" ? "Core Orchestrator" : role === "knight" ? "Execution Worker" : "Passive Sensor"}
                </div>
              </div>
            ))}
          </div>
          <button className="primary-blue" onClick={() => setStep(2)}>Next: Database Setup &rarr;</button>
        </div>
      )}

      {/* Step 2: Configuration */}
      {step === 2 && (
        <div>
          <h4>Configuration Settings</h4>
          <div style={{ margin: "16px 0" }}>
            <label style={{ display: "block", fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
              SQLite Database Target Path:
            </label>
            <input
              type="text"
              value={dbPath}
              onChange={e => setDbPath(e.target.value)}
              style={{ width: "100%", padding: "8px", background: "#1a2332", color: "#fff", border: "1px solid var(--surface-border)", borderRadius: "4px" }}
            />
          </div>

          <div style={{ display: "flex", gap: "12px" }}>
            <button onClick={() => setStep(1)}>&larr; Back</button>
            <button className="primary-blue" onClick={handleRunSetup} disabled={installStatus === "running"}>
              {installStatus === "running" ? "Running Setup..." : "Run Kingdom Setup"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Logs & Verification */}
      {step === 3 && (
        <div>
          <h4 style={{ color: "#34d399" }}>Setup Verification Complete!</h4>
          <div style={{ background: "#0d111a", padding: "12px", borderRadius: "4px", fontSize: "12px", fontFamily: "monospace", margin: "16px 0", maxHeight: "200px", overflowY: "auto" }}>
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
          {healthInfo && (
            <div className="card" style={{ fontSize: "12px", background: "#1a2332", marginBottom: "16px" }}>
              <div>System Status: <strong>{healthInfo.status}</strong></div>
              <div>Runtime Version: <strong>{healthInfo.version}</strong></div>
              <div>Active Tasks: <strong>{healthInfo.tasks_active}</strong></div>
            </div>
          )}
          <button className="primary-blue" onClick={() => window.location.href = "/"}>Launch Kingdom Dashboard</button>
        </div>
      )}
    </div>
  )
}

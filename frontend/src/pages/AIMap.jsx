import React, { useState, useEffect } from "react"
import api from "../api"
import AIMapGraph from "../components/graphs/AIMapGraph"
import BundleBuilder from "../components/skills/BundleBuilder"

export default function AIMap() {
  const [skills, setSkills] = useState([])
  const [bundles, setBundles] = useState([])
  const [departments, setDepartments] = useState([])
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [resolution, setResolution] = useState(null)
  const [showBundleBuilder, setShowBundleBuilder] = useState(false)
  const [chosenDepts, setChosenDepts] = useState([])

  const loadData = () => {
    api.get("/skills").then(r => {
      setSkills(r.data || [])
      if (!selectedSkill && r.data && r.data.length > 0) {
        selectSkill(r.data[0])
      }
    }).catch(() => {})

    api.get("/skills/bundles").then(r => setBundles(r.data || [])).catch(() => {})
    api.get("/skills/departments").then(r => setDepartments(r.data || [])).catch(() => {})
  }

  useEffect(() => {
    loadData()
  }, [])

  const selectSkill = (sk) => {
    setSelectedSkill(sk)
    api.get(`/skills/${sk.id}/dependencies`).then(r => {
      setResolution(r.data)
      setChosenDepts(r.data.required_departments || [])
    }).catch(() => setResolution(null))
  }

  const handleInstall = async (skId, scope) => {
    const depts = scope === "none" ? [] : scope === "choose" ? chosenDepts : null
    await api.post(`/skills/${skId}/install`, { chosen_departments: depts })
    loadData()
  }

  const handleActivate = async (skId) => {
    await api.post(`/skills/${skId}/activate`)
    loadData()
  }

  const handleDeactivate = async (skId) => {
    await api.post(`/skills/${skId}/deactivate`)
    loadData()
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <h2>AI Skill Map & Dependency Resolution Engine</h2>
        <button className="primary-blue" onClick={() => setShowBundleBuilder(true)}>
          + Create Skill Bundle
        </button>
      </div>

      {showBundleBuilder && (
        <BundleBuilder
          skills={skills}
          onBundleCreated={loadData}
          onClose={() => setShowBundleBuilder(false)}
        />
      )}

      {/* Main Grid: Skills Browser & Skill Inspector */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "20px", marginTop: "16px" }}>
        <div>
          <h4>Available AI Skills ({skills.length})</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "12px", margin: "12px 0" }}>
            {skills.map(sk => (
              <div
                key={sk.id}
                onClick={() => selectSkill(sk)}
                className="card"
                style={{
                  cursor: "pointer",
                  border: selectedSkill?.id === sk.id ? "1px solid var(--accent-blue)" : "1px solid var(--surface-border)",
                  background: selectedSkill?.id === sk.id ? "var(--surface-hover)" : "var(--surface-dark)"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontWeight: "700" }}>{sk.name}</span>
                  <span className={`badge badge-${sk.state}`}>{sk.state}</span>
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>{sk.department} | v{sk.version}</div>
              </div>
            ))}
          </div>

          {bundles.length > 0 && (
            <div style={{ marginTop: "24px" }}>
              <h4>Skill Bundles ({bundles.length})</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "12px", marginTop: "10px" }}>
                {bundles.map(b => (
                  <div key={b.id} className="card">
                    <div style={{ fontWeight: "700", color: "#60a5fa" }}>{b.name}</div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>{b.description}</div>
                    <div style={{ fontSize: "11px", marginTop: "6px", color: "var(--text-muted)" }}>Included Skills: {b.skill_ids.length}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: "24px" }}>
            <AIMapGraph />
          </div>
        </div>

        {/* Skill Inspector Panel */}
        <div className="card" style={{ height: "fit-content" }}>
          <div className="card-title">Skill Inspector & Dependencies</div>
          {selectedSkill && resolution ? (
            <div>
              <h3 style={{ fontSize: "16px", marginBottom: "8px" }}>{selectedSkill.name}</h3>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px" }}>{selectedSkill.description}</p>

              <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                <span className={`badge badge-${resolution.readiness_status === "READY" ? "ready" : "missing"}`}>
                  Readiness: {resolution.readiness_status}
                </span>
                <span className={`badge badge-${selectedSkill.state}`}>
                  Status: {selectedSkill.state}
                </span>
              </div>

              {/* Department Scope Controls */}
              <div style={{ marginBottom: "12px", background: "#1a2332", padding: "10px", borderRadius: "4px" }}>
                <div style={{ fontSize: "12px", fontWeight: "600", marginBottom: "6px" }}>Installation Scope:</div>
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                  <button style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => handleInstall(selectedSkill.id, "all")}>
                    Install All Required
                  </button>
                  <button style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => handleInstall(selectedSkill.id, "none")}>
                    Install None
                  </button>
                </div>
              </div>

              {/* Process-Level Dependency Explanations */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{ fontSize: "12px", fontWeight: "600", marginBottom: "6px" }}>Process Dependency Explanations:</div>
                {(resolution.processes || []).map((p, idx) => (
                  <div key={idx} style={{ background: "#0d111a", padding: "8px", borderRadius: "4px", marginBottom: "6px", fontSize: "11px" }}>
                    <div style={{ fontWeight: "700", color: "#60a5fa" }}>Process: {p.name}</div>
                    <div style={{ color: "var(--text-muted)" }}>Required Departments: {p.required_departments.join(", ")}</div>
                    <div style={{ color: "var(--text-muted)" }}>Required Tools: {p.required_tools.join(", ")}</div>
                  </div>
                ))}
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
                {selectedSkill.state === "saved" && (
                  <button className="primary-blue" onClick={() => handleInstall(selectedSkill.id, "all")}>Install Skill</button>
                )}
                {selectedSkill.state === "installed" && (
                  <button className="primary-blue" onClick={() => handleActivate(selectedSkill.id)}>Activate Skill</button>
                )}
                {selectedSkill.state === "active" && (
                  <button onClick={() => handleDeactivate(selectedSkill.id)}>Deactivate Skill</button>
                )}
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>Select a skill to inspect dependencies.</p>
          )}
        </div>
      </div>
    </div>
  )
}

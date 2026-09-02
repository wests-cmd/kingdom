import React, { useState } from "react"
import api from "../../api"

export default function BundleBuilder({ skills, onBundleCreated, onClose }) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [selectedSkillIds, setSelectedSkillIds] = useState([])

  const toggleSkill = (id) => {
    if (selectedSkillIds.includes(id)) {
      setSelectedSkillIds(selectedSkillIds.filter(s => s !== id))
    } else {
      setSelectedSkillIds([...selectedSkillIds, id])
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim() || selectedSkillIds.length === 0) return
    await api.post("/skills/bundles", { name, description, skill_ids: selectedSkillIds })
    onBundleCreated()
    onClose()
  }

  return (
    <div className="card" style={{ background: "#111827", border: "1px solid var(--accent-blue)", padding: "20px", marginTop: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "12px" }}>
        <h3>Create Skill Bundle</h3>
        <button onClick={onClose}>Cancel</button>
      </div>

      <form onSubmit={handleCreate}>
        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "12px", color: "var(--text-muted)" }}>Bundle Name:</label>
          <input
            type="text"
            placeholder="e.g. My Investment Research Toolkit"
            value={name}
            onChange={e => setName(e.target.value)}
            style={{ width: "100%", padding: "8px", background: "#1e2638", color: "#fff", border: "1px solid var(--surface-border)", borderRadius: "4px" }}
          />
        </div>

        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "12px", color: "var(--text-muted)" }}>Description:</label>
          <input
            type="text"
            placeholder="Bundle description..."
            value={description}
            onChange={e => setDescription(e.target.value)}
            style={{ width: "100%", padding: "8px", background: "#1e2638", color: "#fff", border: "1px solid var(--surface-border)", borderRadius: "4px" }}
          />
        </div>

        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", fontSize: "12px", color: "var(--text-muted)", marginBottom: "6px" }}>Select Included Skills:</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px" }}>
            {skills.map(sk => (
              <label key={sk.id} style={{ display: "flex", alignItems: "center", gap: "8px", background: "#1a2332", padding: "8px", borderRadius: "4px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={selectedSkillIds.includes(sk.id)}
                  onChange={() => toggleSkill(sk.id)}
                />
                <span style={{ fontSize: "12px" }}>{sk.name}</span>
              </label>
            ))}
          </div>
        </div>

        <button type="submit" className="primary-blue" disabled={selectedSkillIds.length === 0}>
          Save & Create Bundle ({selectedSkillIds.length} skills)
        </button>
      </form>
    </div>
  )
}

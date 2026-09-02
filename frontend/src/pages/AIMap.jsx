import React, { useState } from "react"
import AIMapGraph from "../components/graphs/AIMapGraph"

export default function AIMap() {
  const [activeType, setActiveType] = useState("Task Map")
  const mapTypes = ["Task Map", "Memory Map", "Swarm Map", "Security Map", "Evolution Map"]

  return (
    <div>
      <h2>AI Intelligence Maps</h2>

      <div style={{ display: "flex", gap: "8px", margin: "16px 0" }}>
        {mapTypes.map(t => (
          <button
            key={t}
            className={activeType === t ? "primary-red" : ""}
            onClick={() => setActiveType(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "16px" }}>
        <div className="card-title">Active Map Spec</div>
        <div style={{ fontSize: "14px", fontWeight: "600" }}>{activeType} (Schema v40.1)</div>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
          Structured intelligence graph containing relationships, weights, trust provenance, and cognitive routing outcomes.
        </div>
      </div>

      <AIMapGraph />
    </div>
  )
}

import React, { useState, useEffect } from "react"
import api from "../api"
import SwarmGraph from "../components/graphs/SwarmGraph"

export default function Swarm() {
  const [knights, setKnights] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get("/knights")
      .then(res => setKnights(res.data || []))
      .catch(() => setKnights([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h2>Swarm & Knights Runtime</h2>
      {loading ? <p>Loading knights...</p> : (
        <div style={{ marginBottom: "16px" }}>
          <h4>Registered Knights ({knights.length})</h4>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {knights.map(k => (
              <li key={k.id} style={{ background: "#222", padding: "8px 12px", borderRadius: "4px", marginBottom: "6px" }}>
                <strong>{k.id}</strong> ({k.role}) — Status: <span style={{ color: k.status === "idle" ? "lightgreen" : "orange" }}>{k.status}</span> — Health: {k.health}
              </li>
            ))}
          </ul>
        </div>
      )}
      <SwarmGraph />
    </div>
  )
}

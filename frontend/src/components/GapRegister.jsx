import React, { useState, useEffect } from "react"
import api from "../api"

export default function GapRegister() {
  const [data, setData] = useState({ items: [], summary: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get("/system/gap-register")
      .then(res => {
        setData(res.data || { items: [], summary: {} })
        setLoading(false)
      })
      .catch(err => {
        setError("Failed to load gap register")
        setLoading(false)
      })
  }, [])

  if (loading) return <p className="muted">Loading gap register…</p>
  if (error) return <p className="muted" role="alert">{error}</p>

  const items = data.items || []
  const summary = data.summary || {}

  const getStatusColor = (status) => {
    switch (status) {
      case "verified": return "var(--accent-green)"
      case "partial": return "var(--accent-orange)"
      case "blocked": return "var(--accent-red)"
      default: return "var(--text-muted)"
    }
  }

  return (
    <section className="panel gap-register-panel" style={{ marginTop: "20px" }}>
      <div className="section-heading">
        <h2>Capability & Architecture Gap Register</h2>
        <span className="badge" style={{ fontSize: "12px", background: "var(--surface-dark)", padding: "4px 8px", borderRadius: "4px" }}>
          {summary.verified || 0} Verified · {summary.partial || 0} Partial · {summary.missing || 0} Missing
        </span>
      </div>
      <p className="muted">
        Live execution evidence and progress tracking towards the general-purpose autonomous AI harness.
      </p>

      <div style={{ overflowX: "auto", marginTop: "12px" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--surface-border)" }}>
              <th style={{ padding: "8px" }}>Capability</th>
              <th style={{ padding: "8px" }}>Priority</th>
              <th style={{ padding: "8px" }}>Status</th>
              <th style={{ padding: "8px" }}>Existing Implementation</th>
              <th style={{ padding: "8px" }}>Missing Work</th>
              <th style={{ padding: "8px" }}>Test Evidence</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} style={{ borderBottom: "1px solid var(--surface-border)" }}>
                <td style={{ padding: "8px", fontWeight: "600" }}>{item.capability}</td>
                <td style={{ padding: "8px" }}>
                  <span style={{
                    padding: "2px 6px",
                    borderRadius: "4px",
                    fontSize: "11px",
                    fontWeight: "bold",
                    background: item.priority === "P0" ? "rgba(220, 38, 38, 0.2)" : "rgba(234, 179, 8, 0.2)",
                    color: item.priority === "P0" ? "var(--accent-red)" : "var(--accent-orange)"
                  }}>
                    {item.priority}
                  </span>
                </td>
                <td style={{ padding: "8px" }}>
                  <span style={{ color: getStatusColor(item.status), fontWeight: "600", textTransform: "capitalize" }}>
                    {item.status}
                  </span>
                </td>
                <td style={{ padding: "8px", color: "var(--text-muted)" }}>{item.existing_implementation}</td>
                <td style={{ padding: "8px", color: "var(--text-muted)" }}>{item.missing_work}</td>
                <td style={{ padding: "8px", fontFamily: "monospace", fontSize: "11px" }}>{item.test_evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

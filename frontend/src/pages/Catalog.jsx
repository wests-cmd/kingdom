import React, { useState, useEffect } from "react"
import { listCatalogApis, triggerCatalogSync, verifyCatalogProvider } from "../api"

export default function Catalog() {
  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState("")

  const loadCatalog = async () => {
    try {
      setLoading(true)
      const data = await listCatalogApis({ category: categoryFilter || undefined })
      setProviders(data || [])
    } catch (err) {
      console.error("Failed to load catalog:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCatalog()
  }, [categoryFilter])

  const handleSync = async () => {
    try {
      setSyncing(true)
      await triggerCatalogSync()
      await loadCatalog()
    } catch (err) {
      alert("Sync failed: " + err.message)
    } finally {
      setSyncing(false)
    }
  }

  const handleVerify = async (providerId) => {
    try {
      const res = await verifyCatalogProvider(providerId)
      alert(`Verification result: ${res.verification_status} (${res.response_time_ms || 0}ms)`)
      loadCatalog()
    } catch (err) {
      alert("Verification failed: " + err.message)
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <h2>API Provider Catalog (Power / Admin)</h2>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            Inspect, search, and verify public and custom API providers mapped to Kingdom capabilities.
          </p>
        </div>
        <button className="primary-red" disabled={syncing} onClick={handleSync}>
          {syncing ? "Syncing..." : "Sync Public APIs"}
        </button>
      </div>

      <div style={{ margin: "16px 0", display: "flex", gap: "12px" }}>
        <input
          type="text"
          placeholder="Filter by category..."
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ padding: "8px 12px", background: "#111", border: "1px solid var(--surface-border)", color: "#fff", width: "240px" }}
        />
      </div>

      {loading ? (
        <p>Loading API Provider Catalog...</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="table" style={{ width: "100%", textAlign: "left", fontSize: "13px" }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Auth Type</th>
                <th>HTTPS</th>
                <th>Verification</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: "600" }}>{p.name}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{p.description || "No description provided"}</div>
                  </td>
                  <td>{p.category || "General"}</td>
                  <td><span style={{ fontSize: "11px", background: "#222", padding: "2px 6px", borderRadius: "4px" }}>{p.auth_type}</span></td>
                  <td>{p.https_supported ? "Yes" : "No"}</td>
                  <td>
                    <span style={{ color: p.verification_status === "verified" ? "var(--accent-green)" : "var(--text-muted)" }}>
                      {p.verification_status}
                    </span>
                  </td>
                  <td>
                    <button style={{ fontSize: "11px", padding: "4px 8px" }} onClick={() => handleVerify(p.id)}>
                      Verify
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

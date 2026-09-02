import React, { useState, useEffect } from "react"
import api from "../../api"

export default function ApprovalsView() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchApprovals = async () => {
    try {
      setLoading(true)
      const res = await api.get("/security/approvals?status=pending")
      setApprovals(res.data || [])
      setError(null)
    } catch (err) {
      setError("Failed to load security approvals")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
    const interval = setInterval(fetchApprovals, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleApprove = async (id) => {
    try {
      await api.post(`/security/approvals/${id}/approve`, { approving_identity: "admin" })
      fetchApprovals()
    } catch (err) {
      alert("Error approving request: " + (err.response?.data?.detail || err.message))
    }
  }

  const handleDeny = async (id) => {
    try {
      await api.post(`/security/approvals/${id}/deny`, { denying_identity: "admin", reason: "Denied via UI" })
      fetchApprovals()
    } catch (err) {
      alert("Error denying request: " + (err.response?.data?.detail || err.message))
    }
  }

  return (
    <div className="security-approvals-card" style={{ border: "1px solid #333", padding: "16px", borderRadius: "8px", marginTop: "16px" }}>
      <h3>Security Approvals Boundary</h3>
      {loading && <p>Loading pending requests...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {!loading && approvals.length === 0 && <p style={{ color: "#888" }}>No pending security approval requests.</p>}

      {approvals.map((req) => (
        <div key={req.approval_id} style={{ background: "#222", padding: "12px", borderRadius: "6px", marginBottom: "8px" }}>
          <div><strong>Requested Capability:</strong> {req.requested_capability}</div>
          <div><strong>Node:</strong> {req.requesting_node} ({req.component})</div>
          <div><strong>Action:</strong> {req.action}</div>
          <div><strong>Risk Level:</strong> <span style={{ color: req.risk_level === "HIGH" ? "red" : "orange" }}>{req.risk_level}</span></div>
          <div><strong>Reason:</strong> {req.reason}</div>
          <div style={{ marginTop: "8px" }}>
            <button onClick={() => handleApprove(req.approval_id)} style={{ marginRight: "8px", background: "green", color: "#fff", border: "none", padding: "6px 12px", borderRadius: "4px", cursor: "pointer" }}>
              Approve
            </button>
            <button onClick={() => handleDeny(req.approval_id)} style={{ background: "red", color: "#fff", border: "none", padding: "6px 12px", borderRadius: "4px", cursor: "pointer" }}>
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

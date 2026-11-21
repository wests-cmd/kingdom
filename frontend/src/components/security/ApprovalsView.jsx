import React, { useState, useEffect } from "react"
import api from "../../api"

export default function ApprovalsView() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState('')

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

  const decide = async (id, decision) => {
    if (busy) return
    setBusy(id)
    setActionError('')
    try {
      if (decision === 'approve') await api.post(`/security/approvals/${id}/approve`, {})
      else await api.post(`/security/approvals/${id}/deny`, { reason: 'Denied via UI' })
      await fetchApprovals()
    } catch {
      setActionError('Could not record the approval decision. Refresh and review the request again before trying.')
    } finally {setBusy('')}
  }

  return (
    <div className="security-approvals-card" style={{ border: "1px solid #333", padding: "16px", borderRadius: "8px", marginTop: "16px" }}>
      <h3>Requests that need your decision</h3>
      <p>Kingdom pauses certain actions so you can check <strong>who is asking, what would be done, and the exact parameters</strong>. A request is not permission by itself. Approve only actions you recognize; otherwise deny them.</p>
      {loading && <p role="status">Checking pending requests…</p>}
      {error && <p role="alert">Could not check approvals. These requests may be out of date. Refresh before deciding.</p>}
      {actionError && <p role="alert">{actionError}</p>}
      {!loading && !error && approvals.length === 0 && <p>No requests are currently waiting for a decision.</p>}

      {approvals.map((req) => (
        <div key={req.approval_id} style={{ background: "var(--input-bg)", padding: "12px", borderRadius: "6px", marginBottom: "8px" }}>
          <div><strong>Permission requested:</strong> {req.capability || 'Not reported'}</div>
          <div><strong>Requesting computer and agent:</strong> {req.requesting_node || 'Not reported'} ({req.requesting_actor || 'Not reported'})</div>
          <div><strong>Action it wants to take:</strong> {req.operation || 'Not reported'}</div>
          <div><strong>Reported risk:</strong> {req.risk_level || 'Not reported'}</div>
          <div><strong>Why it says it needs this:</strong> {req.reason || 'No reason reported'}</div>
          <div><strong>Exact action details — check before approving:</strong> <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(req.parameters ?? {}, null, 2)}</pre></div>
          <div><strong>Request expires:</strong> {req.expires_at ? new Date(req.expires_at).toLocaleString() : 'Not reported'}</div>
          <p className="muted">Approving submits this request for Kingdom's existing permission checks. It does not mean every future action is approved. Denying this request does not remove your other devices.</p>
          <div style={{ marginTop: "8px" }}>
            <button disabled={!!busy || !!error} onClick={() => decide(req.approval_id,'approve')} style={{ marginRight: "8px", background: "var(--accent-primary)", color: "var(--accent-on-primary)", border: "none", padding: "6px 12px", borderRadius: "4px", cursor: "pointer" }}>
              {busy === req.approval_id ? 'Saving…' : 'Approve this request'}
            </button>
            <button disabled={!!busy || !!error} onClick={() => decide(req.approval_id,'deny')} style={{ background: "var(--input-bg)", color: "var(--text-main)", border: "1px solid var(--surface-border)", padding: "6px 12px", borderRadius: "4px", cursor: "pointer" }}>
              Deny this request
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

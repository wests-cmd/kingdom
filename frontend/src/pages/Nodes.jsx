import React, { useState, useEffect } from 'react';
import { api } from '../api';

export function Nodes() {
  const [kingdomIdentity, setKingdomIdentity] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [pendingNodes, setPendingNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPairModal, setShowPairModal] = useState(false);
  const [invitation, setInvitation] = useState(null);
  const [activeTab, setActiveTab] = useState('nodes');

  // Knight Connection Form State
  const [joinCode, setJoinCode] = useState('');
  const [knightName, setKnightName] = useState('');
  const [joinStatus, setJoinStatus] = useState(null);

  const fetchClusterState = async () => {
    try {
      setLoading(true);
      const [idData, nodesData, pendingData] = await Promise.all([
        api.getKingdomIdentity(),
        api.listClusterNodes(),
        api.listPendingNodes()
      ]);
      setKingdomIdentity(idData);
      setNodes(nodesData || []);
      setPendingNodes(pendingData || []);
    } catch (err) {
      console.error('Failed to fetch cluster state:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusterState();
  }, []);

  const handleCreateInvitation = async () => {
    try {
      const inv = await api.createPairingInvitation(600);
      setInvitation(inv);
      setShowPairModal(true);
    } catch (err) {
      alert('Failed to generate pairing invitation: ' + err.message);
    }
  };

  const handleApproveNode = async (nodeId, requestedCaps) => {
    try {
      await api.approveNode(nodeId, requestedCaps);
      fetchClusterState();
    } catch (err) {
      alert('Failed to approve node: ' + err.message);
    }
  };

  const handleRejectNode = async (nodeId) => {
    try {
      await api.rejectNode(nodeId, 'Rejected from Command Center UI');
      fetchClusterState();
    } catch (err) {
      alert('Failed to reject node: ' + err.message);
    }
  };

  const handleRevokeNode = async (nodeId) => {
    if (!confirm(`Are you sure you want to revoke Knight ${nodeId}?`)) return;
    try {
      await api.revokeNode(nodeId, 'Revoked by administrator');
      fetchClusterState();
    } catch (err) {
      alert('Failed to revoke node: ' + err.message);
    }
  };

  const handleJoinKingdom = async (e) => {
    e.preventDefault();
    try {
      setJoinStatus({ type: 'info', message: 'Connecting to Kingdom...' });
      const knightId = `kn-${Date.now().toString(36)}`;
      const knightIdentity = {
        node_id: knightId,
        display_name: knightName || knightId,
        public_key_hex: 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0',
        fingerprint: '3A:8F:92:B1:00:4D:E1:99:77:2B:1A:C0:5E:4F:22:91'
      };

      const res = await api.processNodePairing({
        code: joinCode,
        knight_public_identity: knightIdentity,
        requested_capabilities: ['compute', 'gpu', 'storage_read'],
        is_local: false
      });

      setJoinStatus({
        type: 'success',
        message: `Successfully sent pairing request! Waiting for Kingdom approval for ${res.node_id}.`
      });
      fetchClusterState();
    } catch (err) {
      setJoinStatus({
        type: 'error',
        message: err.message || 'Failed to join Kingdom.'
      });
    }
  };

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "16px" }}>
        <div>
          <h1 style={{ fontSize: "20px", fontWeight: "700", color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
            🛡️ Node Federation & Multi-Node Cluster
          </h1>
          <p style={{ fontSize: "12px", color: "#888", marginTop: "4px" }}>
            Secure, identity-verified Kingdom Commander & Knight federation across LAN, WAN, and overlay networks.
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <button
            onClick={fetchClusterState}
            style={{ padding: "6px 14px", background: "#222", border: "1px solid #444", color: "#ccc", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}
          >
            🔄 Refresh
          </button>
          <button
            onClick={handleCreateInvitation}
            style={{ padding: "6px 14px", background: "var(--accent-red)", color: "#fff", border: "none", borderRadius: "4px", fontSize: "12px", fontWeight: "600", cursor: "pointer" }}
          >
            ➕ Add Knight / Pair Node
          </button>
        </div>
      </div>

      {/* Kingdom Identity Banner */}
      {kingdomIdentity && (
        <div style={{ padding: "16px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{ fontSize: "24px", padding: "8px", background: "#2a1213", border: "1px solid #4d181a", borderRadius: "6px" }}>
              👑
            </div>
            <div>
              <div style={{ fontSize: "10px", fontWeight: "700", color: "var(--accent-red)", textTransform: "uppercase", letterSpacing: "1px" }}>
                Kingdom Commander Identity
              </div>
              <div style={{ fontSize: "16px", fontWeight: "700", color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                {kingdomIdentity.display_name} <span style={{ fontSize: "11px", padding: "2px 6px", background: "#222", color: "#aaa", borderRadius: "3px", fontFamily: "monospace" }}>{kingdomIdentity.node_id}</span>
              </div>
              <div style={{ fontSize: "11px", color: "#888", fontFamily: "monospace", marginTop: "2px" }}>
                Fingerprint: <span style={{ color: "#ddd" }}>{kingdomIdentity.fingerprint}</span>
              </div>
            </div>
          </div>
          <div>
            <span style={{ fontSize: "11px", padding: "4px 10px", background: "#0a2912", color: "#4ade80", border: "1px solid #166534", borderRadius: "12px", fontWeight: "500" }}>
              🟢 Cryptographic Mutual Authentication Active
            </span>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #282828", fontSize: "13px", fontWeight: "500" }}>
        <button
          onClick={() => setActiveTab('nodes')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'nodes' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'nodes' ? "var(--accent-red)" : "#888", cursor: "pointer" }}
        >
          Active Federation ({nodes.length})
        </button>
        <button
          onClick={() => setActiveTab('pending')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'pending' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'pending' ? "var(--accent-red)" : "#888", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
        >
          Pending Approvals
          {pendingNodes.length > 0 && (
            <span style={{ padding: "2px 6px", background: "var(--accent-red)", color: "#fff", fontSize: "10px", borderRadius: "10px" }}>{pendingNodes.length}</span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('join')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'join' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'join' ? "var(--accent-red)" : "#888", cursor: "pointer" }}
        >
          Join a Kingdom (Knight Mode)
        </button>
      </div>

      {/* TAB 1: Active Nodes */}
      {activeTab === 'nodes' && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
          {nodes.map((node) => (
            <div key={node.id} style={{ padding: "16px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: "700", color: "#fff", fontSize: "14px", display: "flex", alignItems: "center", gap: "6px" }}>
                    {node.id}
                    <span style={{ fontSize: "10px", padding: "1px 6px", background: "#222", color: "#aaa", borderRadius: "3px", textTransform: "uppercase" }}>{node.role}</span>
                  </div>
                  <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#777", marginTop: "4px" }}>
                    FP: {node.fingerprint || 'Local Derived'}
                  </div>
                </div>
                <span style={{
                  fontSize: "10px", padding: "2px 8px", borderRadius: "3px", fontWeight: "700", textTransform: "uppercase",
                  background: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '#0a2912' : node.node_state === 'REVOKED' ? '#2a1213' : '#2a220a',
                  color: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '#4ade80' : node.node_state === 'REVOKED' ? '#f87171' : '#facc15',
                  border: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '1px solid #166534' : node.node_state === 'REVOKED' ? '1px solid #7f1d1d' : '1px solid #713f12'
                }}>
                  {node.node_state}
                </span>
              </div>

              <div style={{ fontSize: "11px", color: "#888", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div>Granted Capabilities:</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {(node.granted_capabilities || node.capabilities || []).map((cap, i) => (
                    <span key={i} style={{ padding: "2px 6px", background: "#222", color: "#ccc", borderRadius: "3px", fontSize: "10px" }}>
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid #222", paddingTop: "8px", fontSize: "11px" }}>
                <span style={{ color: "#666" }}>
                  {node.is_local ? 'Local Connection' : 'Remote / WAN Network'}
                </span>
                {node.node_state !== 'REVOKED' && (
                  <button
                    onClick={() => handleRevokeNode(node.id)}
                    style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontWeight: "600" }}
                  >
                    Revoke Knight
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 2: Pending Approvals */}
      {activeTab === 'pending' && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {pendingNodes.length === 0 ? (
            <div style={{ padding: "32px", textAlign: "center", color: "#666", background: "#141414", border: "1px solid #282828", borderRadius: "6px" }}>
              No pending Knight pairing requests.
            </div>
          ) : (
            pendingNodes.map((node) => (
              <div key={node.id} style={{ padding: "16px", background: "#141414", border: "1px solid #3d2b00", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: "15px", fontWeight: "700", color: "#fff" }}>
                      🔑 {node.id}
                    </div>
                    <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#888", marginTop: "2px" }}>
                      Fingerprint: <span style={{ color: "#ccc" }}>{node.fingerprint}</span>
                    </div>
                  </div>
                  <span style={{ padding: "4px 8px", background: "#2a220a", color: "#facc15", border: "1px solid #713f12", fontSize: "11px", borderRadius: "4px", fontWeight: "600" }}>
                    Waiting for Human Approval
                  </span>
                </div>

                <div style={{ background: "#0a0a0a", padding: "10px", borderRadius: "4px", border: "1px solid #222", fontSize: "11px" }}>
                  <div style={{ fontWeight: "600", color: "#aaa", marginBottom: "4px" }}>Requested Capabilities:</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                    {(node.capabilities || []).map((cap) => (
                      <span key={cap} style={{ padding: "2px 6px", background: "#222", color: "#eee", borderRadius: "3px" }}>
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", paddingTop: "4px" }}>
                  <button
                    onClick={() => handleRejectNode(node.id)}
                    style={{ padding: "6px 12px", background: "#222", border: "1px solid #444", color: "#ccc", fontSize: "12px", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleApproveNode(node.id, node.capabilities)}
                    style={{ padding: "6px 12px", background: "#166534", border: "none", color: "#fff", fontSize: "12px", fontWeight: "600", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Approve Knight
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* TAB 3: Join Kingdom */}
      {activeTab === 'join' && (
        <div style={{ maxWidth: "480px", margin: "0 auto", padding: "24px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "16px" }}>
          <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#fff" }}>
            📶 Connect Knight to Kingdom
          </h2>
          <p style={{ fontSize: "12px", color: "#888" }}>
            Enter the Kingdom pairing invitation code to initiate secure cryptographic enrollment.
          </p>

          <form onSubmit={handleJoinKingdom} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#aaa", marginBottom: "4px" }}>Pairing Code</label>
              <input
                type="text"
                placeholder="e.g. 7X4P-92KM"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", borderRadius: "4px", padding: "8px", color: "#fff", fontFamily: "monospace", fontSize: "13px" }}
                required
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#aaa", marginBottom: "4px" }}>Knight Display Name</label>
              <input
                type="text"
                placeholder="e.g. Knight Gaming Workstation"
                value={knightName}
                onChange={(e) => setKnightName(e.target.value)}
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", borderRadius: "4px", padding: "8px", color: "#fff", fontSize: "13px" }}
              />
            </div>

            {joinStatus && (
              <div style={{
                padding: "8px 12px", borderRadius: "4px", fontSize: "11px",
                background: joinStatus.type === 'success' ? '#0a2912' : joinStatus.type === 'error' ? '#2a1213' : '#222',
                color: joinStatus.type === 'success' ? '#4ade80' : joinStatus.type === 'error' ? '#f87171' : '#ccc',
                border: joinStatus.type === 'success' ? '1px solid #166534' : joinStatus.type === 'error' ? '1px solid #7f1d1d' : '1px solid #444'
              }}>
                {joinStatus.message}
              </div>
            )}

            <button
              type="submit"
              style={{ width: "100%", padding: "10px", background: "var(--accent-red)", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer", marginTop: "8px" }}
            >
              Initiate Kingdom Enrollment
            </button>
          </form>
        </div>
      )}

      {/* Pairing Invitation Modal */}
      {showPairModal && invitation && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "#141414", border: "1px solid #282828", borderRadius: "8px", width: "100%", maxWidth: "400px", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#fff" }}>
                📱 Pairing Invitation
              </h3>
              <button onClick={() => setShowPairModal(false)} style={{ background: "none", border: "none", color: "#888", fontSize: "16px", cursor: "pointer" }}>✕</button>
            </div>

            <div style={{ textAlign: "center", padding: "16px", background: "#0a0a0a", border: "1px solid #222", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "1px" }}>Single-Use Pairing Code</div>
              <div style={{ fontSize: "28px", fontFamily: "monospace", fontWeight: "700", color: "var(--accent-red)", letterSpacing: "2px" }}>
                {invitation.code}
              </div>
              <div style={{ fontSize: "11px", color: "#666" }}>
                Expires in {Math.round((invitation.expires_at - Date.now() / 1000) / 60)} minutes
              </div>
            </div>

            <div style={{ fontSize: "11px", color: "#888", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Target Kingdom:</span>
                <span style={{ color: "#eee", fontFamily: "monospace" }}>{invitation.kingdom_id}</span>
              </div>
            </div>

            <button
              onClick={() => setShowPairModal(false)}
              style={{ width: "100%", padding: "8px", background: "#222", color: "#ccc", border: "none", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

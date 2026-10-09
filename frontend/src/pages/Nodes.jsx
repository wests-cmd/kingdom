import React, { useState, useEffect } from 'react';
import { api } from '../api';
import DevicePairing from '../components/DevicePairing';
import ConnectDevice from './ConnectDevice';
import CommandGroups from '../components/CommandGroups';
import {deviceLabel,capabilityLabel,fingerprintLabel,nodeStateLabel} from '../components/common/presentation';

export function Nodes() {
  const [kingdomIdentity, setKingdomIdentity] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [pendingNodes, setPendingNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,setError] = useState("");
  const [showPairModal, setShowPairModal] = useState(false);
  const [invitation, setInvitation] = useState(null);
  const [activeTab, setActiveTab] = useState('nodes');

  const fetchClusterState = async () => {
    try {
      setError("");
      const [idData, nodesData, pendingData] = await Promise.all([
        api.getKingdomIdentity(),
        api.listClusterNodes(),
        api.listPendingNodes()
      ]);
      setKingdomIdentity(idData);
      setNodes(nodesData || []);
      setPendingNodes(pendingData || []);
    } catch (err) {
      setError('Could not refresh device records. Check the Kingdom connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusterState();
    const timer = setInterval(fetchClusterState,5000);
    return () => clearInterval(timer);
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


  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px" }}>
      {error && <p role="alert">{error}</p>}
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "16px" }}>
        <div>
          <h1 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
            Nodes and devices
          </h1>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
            Secure, identity-verified Kingdom Commander & Knight federation across LAN, WAN, and overlay networks.
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <button
            onClick={fetchClusterState}
            style={{ padding: "6px 14px", background: "var(--input-bg)", border: "1px solid var(--surface-border)", color: "var(--text-main)", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}
          >
            Refresh
          </button>
          <button
            onClick={handleCreateInvitation}
            style={{ padding: "6px 14px", background: "var(--accent-primary)", color: "var(--accent-on-primary)", border: "none", borderRadius: "4px", fontSize: "12px", fontWeight: "600", cursor: "pointer" }}
          >
            Invite a compute worker
          </button>
        </div>
      </div>

      {/* Kingdom Identity Banner */}
      {kingdomIdentity && (
        <div style={{ padding: "16px", background: "var(--input-bg)", border: "1px solid var(--surface-border)", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{ fontSize: "24px", padding: "8px", background: "#2a1213", border: "1px solid #4d181a", borderRadius: "6px" }}>
              K
            </div>
            <div>
              <div style={{ fontSize: "10px", fontWeight: "700", color: "var(--accent-red)", textTransform: "uppercase", letterSpacing: "1px" }}>
                Kingdom Commander Identity
              </div>
              <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
                {kingdomIdentity.display_name} <span style={{ fontSize: "11px", padding: "2px 6px", background: "var(--input-bg)", color: "var(--text-muted)", borderRadius: "3px", fontFamily: "monospace" }}>{kingdomIdentity.node_id}</span>
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "monospace", marginTop: "2px" }}>
                Fingerprint: <span style={{ color: "var(--text-main)" }}>{kingdomIdentity.fingerprint}</span>
              </div>
            </div>
          </div>
          <div>
            <span style={{ fontSize: "11px", padding: "4px 10px", background: "#0a2912", color: "#4ade80", border: "1px solid #166534", borderRadius: "12px", fontWeight: "500" }}>
              Commander identity available
            </span>
          </div>
        </div>
      )}

      <CommandGroups />
      {/* Navigation Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--surface-border)", fontSize: "13px", fontWeight: "500" }}>
        <button
          onClick={() => setActiveTab('nodes')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'nodes' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'nodes' ? "var(--accent-red)" : "var(--text-muted)", cursor: "pointer" }}
        >
          Active Federation ({nodes.length})
        </button>
        <button
          onClick={() => setActiveTab('pending')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'pending' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'pending' ? "var(--accent-red)" : "var(--text-muted)", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
        >
          Pending Approvals
          {pendingNodes.length > 0 && (
            <span style={{ padding: "2px 6px", background: "var(--accent-primary)", color: "var(--accent-on-primary)", fontSize: "10px", borderRadius: "10px" }}>{pendingNodes.length}</span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('join')}
          style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === 'join' ? "2px solid var(--accent-red)" : "2px solid transparent", background: "none", color: activeTab === 'join' ? "var(--accent-red)" : "var(--text-muted)", cursor: "pointer" }}
        >
          Connect a phone / device
        </button>
      </div>

      {/* TAB 1: Active Nodes */}
      {activeTab === 'nodes' && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
          {nodes.map((node) => (
            <div key={node.id} style={{ padding: "16px", background: "var(--input-bg)", border: "1px solid var(--surface-border)", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: "700", color: "var(--text-main)", fontSize: "14px", display: "flex", alignItems: "center", gap: "6px" }}>
                    {deviceLabel(node.public_identity?.display_name || node.id)}
                    <span style={{ fontSize: "10px", padding: "1px 6px", background: "var(--input-bg)", color: "var(--text-muted)", borderRadius: "3px", textTransform: "uppercase" }}>{deviceLabel(node.role,'Remote device')}</span>
                  </div>
                  <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#777", marginTop: "4px" }}>
                    FP: {fingerprintLabel(node.fingerprint)}
                  </div>
                </div>
                <span style={{
                  fontSize: "10px", padding: "2px 8px", borderRadius: "3px", fontWeight: "700", textTransform: "uppercase",
                  background: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '#0a2912' : node.node_state === 'REVOKED' ? '#2a1213' : '#2a220a',
                  color: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '#4ade80' : node.node_state === 'REVOKED' ? '#f87171' : '#facc15',
                  border: node.node_state === 'CONNECTED' || node.node_state === 'APPROVED' ? '1px solid #166534' : node.node_state === 'REVOKED' ? '1px solid #7f1d1d' : '1px solid #713f12'
                }}>
                  {node.is_local ? `LOCAL / ${nodeStateLabel(node.status)}` : nodeStateLabel(node.node_state)}
                </span>
              </div>

              <div style={{ fontSize: "11px", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div>{node.is_local ? 'Recorded federation grants (local tools are listed in Swarm):' : 'Granted capabilities:'}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {!(node.granted_capabilities || node.capabilities || []).length && <span>None recorded</span>}
                  {(node.granted_capabilities || node.capabilities || []).map((cap, i) => (
                    <span key={i} style={{ padding: "2px 6px", background: "var(--input-bg)", color: "var(--text-main)", borderRadius: "3px", fontSize: "10px" }}>
                      {capabilityLabel(cap)}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--surface-border)", paddingTop: "8px", fontSize: "11px" }}>
                <span style={{ color: "var(--text-muted)" }}>
                  {node.is_local ? 'Built-in worker · managed by the install profile' : 'Remote / WAN Network'}
                </span>
                {!node.is_local && node.node_state !== 'REVOKED' && (
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
            <div style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)", background: "var(--input-bg)", border: "1px solid var(--surface-border)", borderRadius: "6px" }}>
              No pending Knight pairing requests.
            </div>
          ) : (
            pendingNodes.map((node) => (
              <div key={node.id} style={{ padding: "16px", background: "var(--input-bg)", border: "1px solid #3d2b00", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)" }}>
                      {deviceLabel(node.id,'Pending device')}
                    </div>
                    <div style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--text-muted)", marginTop: "2px" }}>
                      Fingerprint: <span style={{ color: "var(--text-main)" }}>{fingerprintLabel(node.fingerprint)}</span>
                    </div>
                  </div>
                  <span style={{ padding: "4px 8px", background: "#2a220a", color: "#facc15", border: "1px solid #713f12", fontSize: "11px", borderRadius: "4px", fontWeight: "600" }}>
                    Waiting for Human Approval
                  </span>
                </div>

                <div style={{ background: "#0a0a0a", padding: "10px", borderRadius: "4px", border: "1px solid var(--surface-border)", fontSize: "11px" }}>
                  <div style={{ fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>Requested Capabilities:</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                    {(node.capabilities || []).map((cap) => (
                      <span key={cap} style={{ padding: "2px 6px", background: "var(--input-bg)", color: "#eee", borderRadius: "3px" }}>
                        {capabilityLabel(cap)}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", paddingTop: "4px" }}>
                  <button
                    onClick={() => handleRejectNode(node.id)}
                    style={{ padding: "6px 12px", background: "var(--input-bg)", border: "1px solid var(--surface-border)", color: "var(--text-main)", fontSize: "12px", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleApproveNode(node.id, node.capabilities)}
                    style={{ padding: "6px 12px", background: "#166534", border: "none", color: "var(--text-main)", fontSize: "12px", fontWeight: "600", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Approve Device / Knight
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* TAB 3: Join Kingdom */}
      {activeTab === 'join' && <><DevicePairing /><ConnectDevice /></>}

      {/* Pairing Invitation Modal */}
      {showPairModal && invitation && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--input-bg)", border: "1px solid var(--surface-border)", borderRadius: "8px", width: "100%", maxWidth: "400px", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)" }}>
                📱 Pairing Invitation
              </h3>
              <button onClick={() => setShowPairModal(false)} style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: "16px", cursor: "pointer" }}>✕</button>
            </div>

            <div style={{ textAlign: "center", padding: "16px", background: "#0a0a0a", border: "1px solid var(--surface-border)", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>Single-Use Pairing Code</div>
              <div style={{ fontSize: "28px", fontFamily: "monospace", fontWeight: "700", color: "var(--accent-red)", letterSpacing: "2px" }}>
                {invitation.code}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Expires in {Math.round((invitation.expires_at - Date.now() / 1000) / 60)} minutes
              </div>
            </div>

            <div style={{ fontSize: "11px", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Target Kingdom:</span>
                <span style={{ color: "#eee", fontFamily: "monospace" }}>{invitation.kingdom_id}</span>
              </div>
            </div>

            <button
              onClick={() => setShowPairModal(false)}
              style={{ width: "100%", padding: "8px", background: "var(--input-bg)", color: "var(--text-main)", border: "none", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

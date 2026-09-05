import axios from "axios"

const api = axios.create({
  baseURL: "http://localhost:8000"
})

export async function fetchSkills() {
  const res = await api.get("/skills");
  return res.data;
}

export async function fetchSkillMap() {
  const res = await api.get("/skills/map");
  return res.data;
}

export async function checkSkillReadiness(skillId) {
  const res = await api.get(`/skills/${skillId}/readiness`);
  return res.data;
}

export async function fetchLearningActivity() {
  const res = await api.get("/learning/activity");
  return res.data;
}

export async function promoteProposal(proposalId, experimentId) {
  const res = await api.post(`/learning/proposals/${proposalId}/promote`, { experiment_id: experimentId });
  return res.data;
}

export async function triggerRollback(skillId, fromVersion, toVersion, reason) {
  const res = await api.post(`/learning/skills/${skillId}/rollback`, { from_version: fromVersion, to_version: toVersion, reason });
  return res.data;
}

export async function getKingdomIdentity() {
  const res = await api.get("/nodes/identity");
  return res.data;
}

export async function listClusterNodes(nodeState) {
  const res = await api.get("/nodes", { params: { node_state: nodeState } });
  return res.data;
}

export async function listPendingNodes() {
  const res = await api.get("/nodes/pending");
  return res.data;
}

export async function createPairingInvitation(ttlSeconds = 600) {
  const res = await api.post(`/nodes/invitation?ttl_seconds=${ttlSeconds}`);
  return res.data;
}

export async function processNodePairing(pairingPayload) {
  const res = await api.post("/nodes/pair", pairingPayload);
  return res.data;
}

export async function approveNode(nodeId, grantedCapabilities = []) {
  const res = await api.post(`/nodes/${nodeId}/approve`, { granted_capabilities: grantedCapabilities });
  return res.data;
}

export async function rejectNode(nodeId, reason = "Rejected by administrator") {
  const res = await api.post(`/nodes/${nodeId}/reject`, { reason });
  return res.data;
}

export async function revokeNode(nodeId, reason = "Administrator revoked node") {
  const res = await api.post(`/nodes/${nodeId}/revoke?reason=${encodeURIComponent(reason)}`);
  return res.data;
}

export const apiHelper = {
  getKingdomIdentity,
  listClusterNodes,
  listPendingNodes,
  createPairingInvitation,
  processNodePairing,
  approveNode,
  rejectNode,
  revokeNode
};

export { apiHelper as api };
export default api;

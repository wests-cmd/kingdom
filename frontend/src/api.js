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

export default api

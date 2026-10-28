// Presentation/request binding only. The authenticated backend verifies trust.
export function reviewMeshDestination(values) {
  const address = new URL(values.remote)
  if (address.username || address.password || address.search || address.hash || address.pathname !== '/' ||
      !(address.protocol === 'https:' || (address.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(address.hostname)))) {
    throw new Error('Use the exact HTTPS authority address without a path or credentials.')
  }
  const invitation = JSON.parse(values.invitation)
  if (!invitation || Array.isArray(invitation) || typeof invitation !== 'object' ||
      typeof invitation.kingdom_id !== 'string' || typeof invitation.kingdom_fingerprint !== 'string' ||
      typeof invitation.invitation_signature !== 'string' || !/^[a-fA-F0-9]{128}$/.test(invitation.invitation_signature)) {
    throw new Error('Use a current signed invitation. An older authority may need an update and a new invitation.')
  }
  return {authority_endpoint: address.origin, invitation}
}

export function retainMeshApproval(values, response, now = Date.now()/1000) {
  if (values.confirmed !== true) throw new Error('Confirm trust before approving this destination.')
  const reviewed = reviewMeshDestination(values)
  if (!response || !/^[a-f0-9]{32}$/.test(response.approval_id) ||
      response.authority_endpoint !== reviewed.authority_endpoint ||
      response.authority_id !== reviewed.invitation.kingdom_id ||
      response.fingerprint !== reviewed.invitation.kingdom_fingerprint ||
      !Number.isFinite(response.expires_at) || response.expires_at <= now || response.expires_at > now + 301) {
    throw new Error('The returned destination approval does not match this request.')
  }
  return {response, inputs: JSON.stringify(values)}
}

export function meshJoinRequest(values, approval, now = Date.now()/1000) {
  if (values.confirmed !== true || !approval || approval.inputs !== JSON.stringify(values) || approval.response.expires_at <= now) {
    throw new Error('Review and approve this exact destination again before connecting.')
  }
  const reviewed = reviewMeshDestination(values)
  return {...reviewed, local_endpoint: values.local, ca_pem: values.ca,
    destination_approval_id: approval.response.approval_id}
}

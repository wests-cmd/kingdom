export function peerConnectionLabel(attempt, peer, now = Date.now() / 1000) {
  if (attempt === 'membership_expired') return 'Temporary membership ended'
  if (['REVOKED','REJECTED','QUARANTINED'].includes(peer?.node_state)) return 'Connection blocked · restricted device'
  if (attempt === 'authorization_held') return 'Connection held · check trust or configuration'
  const age = now - peer?.last_heartbeat
  if (peer?.node_state === 'CONNECTED' && Number.isFinite(age) && age >= 0 && age <= 45) {
    return attempt === 'verified' ? 'Connected' : 'Connected · receiving peer reports'
  }
  return ({verified:'Last exchange verified · awaiting fresh report', retrying:'Retrying connection', endpoint_required:'Needs a reachable address'})[attempt] || attempt
}

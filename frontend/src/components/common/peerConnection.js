export function peerConnectionLabel(attempt, peer, now = Date.now() / 1000) {
  if (attempt === 'membership_expired') return 'Temporary membership ended'
  const age = now - peer?.last_heartbeat
  if (peer?.node_state === 'CONNECTED' && Number.isFinite(age) && age >= 0 && age <= 45) {
    return attempt === 'verified' ? 'Connected' : 'Connected · receiving peer reports'
  }
  return ({verified:'Connection verified', retrying:'Retrying connection', endpoint_required:'Needs a reachable address'})[attempt] || attempt
}

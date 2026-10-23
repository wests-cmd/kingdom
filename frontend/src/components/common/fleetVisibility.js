const states = {
  running:'Working', thinking:'Waiting for the model', waiting_tools:'Waiting for a tool',
  queued:'Queued', waiting_review:'Needs review', needs_review:'Needs review',
  waiting_approval:'Waiting for approval', waiting_authorization:'Waiting for permission',
  completed:'Recorded complete', succeeded:'Recorded complete', failed:'Failed',
  cancelled:'Cancelled', recovery_required:'Recovery needs review', blocked:'Blocked',
  ready:'Ready', paused:'Paused', unknown:'Not reported',
}

export function jobStatus(status) {
  return states[status] || 'Not reported'
}

export function serviceStatus(service) {
  const running = {running:'Running', stopped:'Not running', unknown:'Running state unknown'}[service.state] || 'Running state unknown'
  const startup = {enabled:'Startup enabled', disabled:'Startup disabled', manual:'Started on demand', unknown:'Startup unknown'}[service.startup] || 'Startup unknown'
  return `${running} · ${startup}`
}

export function serviceScope(report) {
  if (report?.scope === 'container') return 'Host services are unavailable inside this container.'
  if (report?.scope === 'user_services') return 'User services only. Startup enabled is configuration, not a verified restart.'
  if (report?.scope === 'windows_services') return 'Windows services only. Desktop startup apps and scheduled tasks are not included.'
  return 'Service scope has not been reported.'
}

export function peerVisibility(node, report) {
  const permitted = ['CONNECTED','APPROVED','DISCONNECTED','RECONNECTING'].includes(node.node_state)
  const current = node.node_state === 'CONNECTED' && report?.state === 'current'
  return {
    current,
    reportState: permitted ? report?.state || 'missing' : (node.node_state || 'unknown').toLowerCase(),
    services: current ? report.services : null,
    activity: current ? report.activity : null,
    receivedAt: current ? report.received_at : null,
  }
}

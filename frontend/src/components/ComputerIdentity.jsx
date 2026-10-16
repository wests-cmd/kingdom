import React from 'react'

export function modelComputer(profile, hierarchy) {
  const configured = profile.computer_id
  const knight = (hierarchy?.knights || []).find(node => (node.id || node.node_id) === configured)
  if (knight) return `Knight: ${knight.public_identity?.display_name || configured} · ${knight.node_state || 'State unavailable'} (configured association)`
  if (configured) return `Computer: ${configured} · configured label; no matching paired Knight`
  return 'Computer not associated · server address alone does not establish a Knight'
}

export default function ComputerIdentity({data, error}) {
  return <section className="panel" style={{minWidth:0, overflowWrap:'anywhere'}} aria-label="Computers and agents">
    <h2>Computers and agents</h2>
    <p>Knights are computers. Knight Apprentices are software agents running on a computer.</p>
    {error && <p role="alert">Computer identities could not be refreshed.</p>}
    {!data ? <p>Loading computer identities…</p> : <>
      <p><strong>Commander computer:</strong> {data.commander?.computer || 'Not reported'} · this Kingdom controller</p>
      <p><strong>Paired Knight computers:</strong> {(data.knights || []).length} · <strong>Knight Apprentices:</strong> {(data.apprentices || []).length}</p>
      {!(data.knights || []).length && <p className="muted">No paired Knight computers are recorded. Local agents and model connections do not create paired computers.</p>}
    </>}
  </section>
}

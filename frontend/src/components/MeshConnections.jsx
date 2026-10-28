import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {peerConnectionLabel} from './common/peerConnection'
import {reviewMeshDestination,retainMeshApproval,meshJoinRequest} from '../meshEnrollment'

export default function MeshConnections({hierarchy}) {
  const {data: mesh, error} = useLiveData('/federation/mesh', 15000)
  const {data: links} = useLiveData('/federation/connections/status', 15000)
  const [local, setLocal] = useState(''), [remote, setRemote] = useState('')
  const [invitation, setInvitation] = useState(''), [ca, setCa] = useState('')
  const [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
  const [approval, setApproval] = useState(null), [confirmed, setConfirmed] = useState(false)
  const values = {local,remote,invitation,ca,confirmed}
  const changed = setter => e => {setter(e.target.value);setApproval(null);setConfirmed(false)}
  let destination = null
  try {destination = reviewMeshDestination(values)} catch {}
  const action = async work => {
    setBusy(true); setMessage('')
    try { await work() } catch (e) { setMessage(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message) }
    finally { setBusy(false) }
  }
  const names = new Map((hierarchy?.knights || []).map(n => [n.node_id || n.id, n.display_username || n.hostname || n.node_id || n.id]))
  const peers = new Map((hierarchy?.knights || []).map(n => [n.node_id || n.id, n]))
  return <section className="panel" aria-label="Automatic Knight connections">
    <h3>Automatic Knight connections</h3>
    <p>Join once, then connect to every approved Knight. Choose one computer to keep the approved member list. This shares connections and activity reports; task permissions stay separate.</p>
    {error && <p role="alert">Connection settings are unavailable. This installation may need its backend updated.</p>}
    {mesh && <p>{mesh.enabled ? `Membership authority: ${names.get(mesh.authority_id) || mesh.authority_id}` : 'Automatic group joining has not been set up on this computer.'}</p>}
    {links && <details><summary>Connection health · {Object.keys(links.peers||{}).filter(id=>peers.has(id)).length} peer Knights</summary><ul>{Object.entries(links.peers || {}).filter(([id])=>peers.has(id)).map(([id, status]) => <li key={id}>{names.get(id) || id}: {peerConnectionLabel(status, peers.get(id))}</li>)}</ul></details>}
    <details><summary>Set up or join this Kingdom</summary>
      <label>This computer’s reachable HTTPS address<input disabled={busy} type="url" value={local} onChange={changed(setLocal)} placeholder="https://this-knight.example" /></label>
      <details><summary>Private certificate trust, if needed</summary><label>Trusted public CA certificates<textarea disabled={busy} value={ca} onChange={changed(setCa)} rows={3} placeholder="Public PEM certificates only" /></label></details>
      <p>The address must expose Kingdom’s signed peer API. A localhost address is only reachable on the same computer.</p>
      <button disabled={busy || !local} onClick={() => action(async () => {
        const {data: identity} = await api.get('/nodes/identity')
        await api.put('/federation/mesh', {authority_id:identity.node_id, local_endpoint:local, ca_pem:ca})
        const {data} = await api.post('/nodes/invitation', {})
        setInvitation(JSON.stringify(data, null, 2)); setApproval(null);setConfirmed(false);setMessage('This computer keeps the member list. Copy its invitation to the joining Knight, then approve the incoming request here.')
      })}>Keep the member list here and create invitation</button>
      <form onSubmit={e => {e.preventDefault(); action(async () => {
        if (!confirmed) throw new Error('Confirm trust before joining this destination.')
        const request = meshJoinRequest(values, approval)
        setApproval(null);setConfirmed(false)
        const {data} = await api.post('/federation/mesh/join', request)
        setMessage(data.message)
      })}}>
        <label>Membership authority’s HTTPS address<input disabled={busy} required type="url" value={remote} onChange={changed(setRemote)} /></label>
        <label>Temporary signed invitation<textarea disabled={busy} required rows={5} value={invitation} onChange={changed(setInvitation)} /></label>
        {destination && <div><p>Review the authority before connecting:</p><dl>
          <dt>Address</dt><dd>{destination.authority_endpoint}</dd>
          <dt>Identity</dt><dd>{destination.invitation.kingdom_id}</dd>
          <dt>Fingerprint</dt><dd>{destination.invitation.kingdom_fingerprint}</dd>
        </dl></div>}
        <label><input disabled={busy} type="checkbox" checked={confirmed} onChange={e=>{setConfirmed(e.target.checked);setApproval(null)}} />I trust this authority and this exact address.</label>
        <button type="button" disabled={busy || !destination || !confirmed} onClick={()=>action(async()=>{
          const {data}=await api.post('/federation/mesh/destinations',reviewMeshDestination(values))
          setApproval(retainMeshApproval(values,data));setMessage('Destination approved for a short connection window. No remote connection has been made yet.')
        })}>Approve this destination</button>
        {approval && <p>Approval expires {new Date(approval.response.expires_at*1000).toLocaleTimeString()}. Changed settings require a new review.</p>}
        <button disabled={busy || !local || !approval || !confirmed}>Join and request approval once</button>
        <p>Approved Knights keep their existing automatic reconnect behavior. This confirmation is for connection setup; it grants no task permissions.</p>
      </form>
    </details>
    {message && <p role="status">{message}</p>}
  </section>
}

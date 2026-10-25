import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {peerConnectionLabel} from './common/peerConnection'

export default function MeshConnections({hierarchy}) {
  const {data: mesh, error} = useLiveData('/federation/mesh', 15000)
  const {data: links} = useLiveData('/federation/connections/status', 15000)
  const [local, setLocal] = useState(''), [remote, setRemote] = useState('')
  const [invitation, setInvitation] = useState(''), [ca, setCa] = useState('')
  const [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
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
      <label>This computer’s reachable HTTPS address<input type="url" value={local} onChange={e => setLocal(e.target.value)} placeholder="https://this-knight.example" /></label>
      <details><summary>Private certificate trust, if needed</summary><label>Trusted public CA certificates<textarea value={ca} onChange={e => setCa(e.target.value)} rows={3} placeholder="Public PEM certificates only" /></label></details>
      <p>The address must expose Kingdom’s signed peer API. A localhost address is only reachable on the same computer.</p>
      <button disabled={busy || !local} onClick={() => action(async () => {
        const {data: identity} = await api.get('/nodes/identity')
        await api.put('/federation/mesh', {authority_id:identity.node_id, local_endpoint:local, ca_pem:ca})
        const {data} = await api.post('/nodes/invitation', {})
        setInvitation(JSON.stringify(data, null, 2)); setMessage('This computer keeps the member list. Copy its invitation to the joining Knight, then approve the incoming request here.')
      })}>Keep the member list here and create invitation</button>
      <form onSubmit={e => {e.preventDefault(); action(async () => {
        const {data} = await api.post('/federation/mesh/join', {authority_endpoint:remote, local_endpoint:local, invitation:JSON.parse(invitation), ca_pem:ca})
        setMessage(data.message)
      })}}>
        <label>Membership authority’s HTTPS address<input required type="url" value={remote} onChange={e => setRemote(e.target.value)} /></label>
        <label>Temporary invitation<textarea required rows={5} value={invitation} onChange={e => setInvitation(e.target.value)} /></label>
        <button disabled={busy || !local}>Join and request approval once</button>
      </form>
    </details>
    {message && <p role="status">{message}</p>}
  </section>
}

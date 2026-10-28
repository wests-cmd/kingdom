import React,{useState} from 'react'
import api from '../api'
export default function KingdomPeers({nodes=[]}){
 const [address,setAddress]=useState(''),[invitation,setInvitation]=useState(''),[exported,setExported]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const peers=nodes.filter(n=>n.public_identity?.node_type==='commander')
 const act=async fn=>{setBusy(true);setMessage('');try{await fn()}catch(e){setMessage(typeof e.response?.data?.detail==='string'?e.response.data.detail:e.message)}finally{setBusy(false)}}
 return <section className="panel"><h2>Connect another Knight</h2><p>These computers are Knights in one Kingdom. Each keeps its own identity, permissions and task evidence.</p>
 <p>Pairing stays in place through sleep, restart and network outages. Offline status does not remove membership. Invitations expire; an approved pairing does not expire because its heartbeat stopped.</p>
 <button disabled={busy} onClick={()=>act(async()=>{const {data}=await api.post('/nodes/invitation',{});setExported(JSON.stringify(data,null,2))})}>Create invitation for another Knight</button>
 {exported&&<label>Share this temporary invitation with the other owner<textarea readOnly rows={6} value={exported}/></label>}
 <form onSubmit={e=>{e.preventDefault();act(async()=>{const {data}=await api.post('/federation/connect',{endpoint:address,invitation:JSON.parse(invitation),capabilities:['compute']});setMessage(data.message)})}}>
 <label>Other Knight URL<input required type="url" value={address} onChange={e=>setAddress(e.target.value)} placeholder="https://other-kingdom.example"/></label>
 <label>Invitation from that Knight<textarea required rows={5} value={invitation} onChange={e=>setInvitation(e.target.value)}/></label><button disabled={busy}>Request connection as a Knight</button></form>
 <p className="muted">Use HTTPS or an existing private SSH tunnel. Invitations do not share owner credentials. Approve incoming requests under Pending Approvals. Existing installations with identical Kingdom IDs need an owner-reviewed identity migration first.</p>
 {peers.map(peer=><div className="record-detail" key={peer.id}><h3>{peer.public_identity.display_name||peer.id}</h3><p>{peer.id} · {peer.node_state}</p><button disabled={busy||!address} onClick={()=>act(async()=>{await api.put(`/federation/${encodeURIComponent(peer.id)}/endpoint`,{endpoint:address});const {data}=await api.post(`/federation/${encodeURIComponent(peer.id)}/reconnect`,{});setMessage(data.connected?'Both Knight identities accepted the reconnection.':'Not connected')})}>Save URL above and reconnect this Knight</button></div>)}
 {message&&<p role="status">{message}</p>}</section>
}

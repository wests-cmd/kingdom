import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

function roleList(text){
 const roles=[...new Set(text.split(',').map(value=>value.trim()).filter(Boolean))]
 if(roles.length>32||roles.some(role=>!/^[a-z][a-z0-9_-]{0,63}$/.test(role)))throw Error('Use up to 32 role names, separated by commas, such as coder or researcher.')
 return roles
}

export default function VaultSyncPanel({project}){
 const {data,error:loadError}=useLiveData('/hierarchy',15000)
 const [peer,setPeer]=useState(''),[roles,setRoles]=useState(''),[direction,setDirection]=useState('send')
 const [destinations,setDestinations]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState(null),[message,setMessage]=useState('')
 const peers=(data?.knights||[]).filter(node=>['APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'].includes(node.node_state)&&(node.public_identity||{}).node_type==='commander')
 const available=peers.some(node=>node.node_id===peer)
 const action=async operation=>{
  setBusy(true);setError('');setResult(null);setMessage('')
  try{await operation()}catch(problem){setError(problem.response?.data?.detail||problem.message||'The operation failed; no completion is claimed.')}
  finally{setBusy(false)}
 }
 const changeGrant=()=>action(async()=>{
  const allowed_roles=roleList(roles)
  const response=await api.put('/vault-sync/grants',{peer,project,direction,allowed_roles})
  setResult(response.data);setMessage(`Saved this Kingdom’s ${direction} grant for this project. The other Kingdom still needs its matching grant.`)
 })
 const push=()=>action(async()=>{
  const {data:receipt}=await api.post('/vault-sync/push',{peer,project})
  setResult(receipt);setMessage('Transfer completed. Kingdom verified the receiving Knight’s signed receipt.')
 })
 const balance=()=>action(async()=>{
  const {data:receipts}=await api.post('/vault-sync/replicate',{project,peers:destinations})
  setResult(receipts)
  setMessage(receipts.status==='replicated'?'Selected Knights received byte-balanced copies. Kingdom verified the receipts.':receipts.status==='empty'?'This project has no notes to transfer.':'Some transfers failed. Successful batches remain saved; inspect the results before retrying.')
 })
 return <section className="panel" style={{minWidth:0,overflowWrap:'anywhere'}} aria-label="Project vault synchronization">
  <h3>Share this project with other Knights</h3>
  <p>Copy project notes between approved Kingdom computers. Pairing a computer does not share notes automatically. Both computers must explicitly allow this project.</p>
  <p className="muted">Source notes stay here. Local edits and trash cause a conflict instead of being overwritten. Copies are untrusted references and never grant tools. Removing a grant stops future transfers; existing copies must be removed on their own computer. Offline computers cannot receive immediate changes or revocations.</p>
  {loadError&&<p role="alert">{loadError}</p>}
  {data&&!peers.length&&<p>No approved Kingdom peers are available. Pair another Kingdom in Nodes &amp; cluster first.</p>}
  <fieldset disabled={busy||!peers.length} style={{minWidth:0}}><legend>1. Choose a computer and allow access</legend>
   <label>Other Knight<select value={peer} onChange={event=>{setPeer(event.target.value);setMessage('');setResult(null)}}><option value="">Choose a paired Kingdom</option>{peers.map(node=><option key={node.node_id} value={node.node_id}>{node.hostname||node.node_id} · {node.node_state}</option>)}</select></label>
   <label>This Kingdom may<select value={direction} onChange={event=>setDirection(event.target.value)}><option value="send">Send project notes to that Knight</option><option value="receive">Receive project notes from that Knight</option></select></label>
   <label>Restricted roles allowed, if needed<input value={roles} onChange={event=>setRoles(event.target.value)} maxLength={2048} placeholder="Leave blank for shared notes only"/></label>
   <p className="muted">Blank means shared notes only. Add explicit role names, separated by commas, only if both computers should hold those restricted notes. Coding roles never gain payment access by copying notes.</p>
   <div style={{display:'flex',flexWrap:'wrap',gap:8}}><button type="button" disabled={!available} onClick={changeGrant}>Save this project access</button><button type="button" disabled={!available} onClick={()=>action(async()=>{const response=await api.delete('/vault-sync/grants',{params:{peer,project,direction}});setResult(response.data);setMessage('Project access removed. Existing remote copies are retained until explicitly removed there.')})}>Remove this project access</button></div>
  </fieldset>
  <fieldset disabled={busy||!peers.length} style={{minWidth:0,marginTop:12}}><legend>2. Copy and verify</legend>
   <p>For a single destination, allow “send” here and “receive” on that Knight for this same project, then transfer. A missing grant, unavailable archive or conflicting edit stops the transfer.</p>
   <button type="button" disabled={!available} onClick={push}>Copy this project to chosen Knight</button>
   <details style={{marginTop:12}}><summary>Distribute copies across several Knights</summary><p>Spread this project’s notes by transferred size across the selected computers. This retains the originals; it does not move the main vault or balance all disk usage. Each destination needs its own matching project grants.</p>
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,220px),1fr))',gap:8}}>{peers.map(node=><label key={node.node_id} style={{display:'flex',alignItems:'flex-start',gap:8}}><input type="checkbox" style={{width:'auto',flex:'0 0 auto'}} checked={destinations.includes(node.node_id)} onChange={event=>setDestinations(previous=>event.target.checked?[...previous,node.node_id]:previous.filter(id=>id!==node.node_id))}/><span>{node.hostname||node.node_id}</span></label>)}</div>
    <button type="button" disabled={!destinations.length||destinations.length>8||destinations.some(id=>!peers.some(node=>node.node_id===id))} onClick={balance}>Distribute copies to selected Knights</button>
   </details>
  </fieldset>
  {busy&&<p role="status">Working with the selected Kingdoms. Completion requires verified receiving receipts…</p>}
  {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {result&&<details><summary>Access or transfer result</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:320,overflow:'auto',maxWidth:'100%'}}>{JSON.stringify(result,null,2)}</pre></details>}
 </section>
}

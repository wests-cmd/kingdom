import React, {useState} from 'react'
import api from '../api'
import TaskTypePriorities from './TaskTypePriorities'
import {computerName} from './common/computerName'
export default function SwarmControls({hierarchy}) {
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false),[drafts,setDrafts]=useState({}),[saved,setSaved]=useState({})
 const nodes=(hierarchy.knights||[]).filter(node=>['APPROVED','CONNECTED'].includes(node.node_state))
 const title=id=>{const node=nodes.find(node=>(node.node_id||node.id)===id);return computerName(node?.display_username,node?.display_computer||node?.hostname,id)}
 const action=async work=>{setBusy(true);try{await work()}catch(error){setMessage(error.response?.data?.detail||'Change failed. Reload current state before retrying.')}finally{setBusy(false)}}
 return <section className="panel swarm-controls" aria-label="Swarm permissions and priorities"><h3>Permissions and priorities</h3>
 <p>Groups organize Knights in the diagram above. These separate controls authorize capabilities for this controller. Reporting lines and groups never grant permissions.</p>
 <h4>What this controller allows each Knight to do</h4>
 {!nodes.length&&<p>No currently approved paired Knights. Pair and verify a computer in Nodes first.</p>}
 {nodes.map(node=>{const id=node.node_id||node.id,current=saved[id]||node.granted_capabilities||[],draft=drafts[id]||current,available=[...new Set([...(node.capabilities||[]),...current])];return <details className="card" key={id}><summary>{title(id)} · {current.length} granted capabilities</summary><p>Destination: {id}. Current approval, execution policy and operating system permissions remain required.</p>
 {available.length?available.map(cap=><label key={cap} style={{display:'block'}}><input type="checkbox" disabled={busy} checked={draft.includes(cap)} onChange={event=>setDrafts(old=>({...old,[id]:event.target.checked?[...draft,cap]:draft.filter(item=>item!==cap)}))}/>{cap}</label>):<p>No capabilities advertised. Missing capabilities are not silently granted.</p>}
 <button disabled={busy||!drafts[id]} onClick={()=>action(async()=>{await api.post(`/nodes/${encodeURIComponent(id)}/capabilities`,{granted_capabilities:draft});const response=await api.get(`/nodes/${encodeURIComponent(id)}/capabilities`);setSaved(old=>({...old,[id]:response.data.granted_capabilities}));setDrafts(old=>{const next={...old};delete next[id];return next});setMessage('Grants saved and read back. Remote execution has not been tested.')})}>Save reviewed capability grants</button></details>})}
 {message&&<p role="status">{message}</p>}<TaskTypePriorities/></section>
}

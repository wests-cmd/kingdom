import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

const labels={current:'Up to date',update_required:'Update needed',unknown:'Version not verified',stale:'Computer unavailable',unconfigured:'No target release selected'}
export default function KingdomUpdates(){
 const {data,error,refresh}=useLiveData('/hierarchy/releases',15000)
 const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const local=data?.knights?.find(k=>k.id==='local')?.installed
 const target=async()=>{setBusy(true);try{await api.put('/hierarchy/releases/desired',{version:local.version,revision:local.revision,source_sha256:local.source_sha256,source_scope:local.source_scope,auto_reconcile:true});await refresh();setMessage('Target saved. Newly connected Knights will be checked against this release.')}catch{setMessage('Could not save the target release.')}finally{setBusy(false)}}
 return <section className="panel" aria-label="Kingdom updates"><h2>Kingdom updates</h2><p>Connected computers report their installed release. New Knights are checked against your saved target; missing reports never count as up to date.</p>
 {error&&<p role="alert">Version reports are unavailable.</p>}
 {data?.desired&&<p>Target: {data.desired.version}{data.desired.revision?` · ${data.desired.revision.slice(0,7)}`:''}</p>}
 <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,240px),1fr))',gap:12}}>{data?.knights?.map(k=><article className="card" key={k.id} style={{minWidth:0,overflowWrap:'anywhere'}}><strong>{k.id==='local'?'This Knight':k.id}</strong><p>{labels[k.status]||'Checking…'}</p><p>{k.installed?.version||'Unknown version'}{k.installed?.revision?` · ${k.installed.revision.slice(0,7)}`:''}</p>{k.installed?.source_evidence==='build_input_manifest'&&<p className="muted">Packaged build metadata; installer verification is separate.</p>}{k.status==='update_required'&&<p>Update adapter: {k.installed?.update_adapter==='configured'?'configured; activation still needs its normal checks':'setup required on this computer'}</p>}</article>)}</div>
 <div className="action-row"><button onClick={refresh}>Check versions</button><button disabled={busy||!local?.source_sha256} onClick={target}>Use this release as target</button></div><p className="muted">Checking does not install software. Installation uses the computer’s configured updater, existing permissions and a verified release.</p>{message&&<p role="status">{message}</p>}</section>
}

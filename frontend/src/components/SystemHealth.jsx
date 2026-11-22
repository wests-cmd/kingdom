import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {healthSummary} from './common/taskVisibility'

function Value({label,value,unit='',note=''}) {
  return <div className="card"><div className="card-title">{label}</div>
    <div className="card-value">{value===null?'—':`${value}${unit}`}</div>
    {note && <small>{note}</small>}
  </div>
}
export default function SystemHealth(){
 const hardware=useLiveData('/system/check',20000)
 const cluster=useLiveData('/orchestration',15000)
 const profiles=useLiveData('/workspace/model-profiles',20000)
 const [provider,setProvider]=useState(null)
 const [providerError,setProviderError]=useState('')
 const [checking,setChecking]=useState(false)
 const [checked,setChecked]=useState(null)
 const statusError=hardware.error||cluster.error||profiles.error
 const ready=!!(hardware.data&&cluster.data&&profiles.data&&!statusError)
 const view=ready?healthSummary({hardware:hardware.data,orchestration:cluster.data,models:profiles.data}):null
 async function checkProviders(){
  setProviderError('');setProvider(null);setChecking(true)
  try {const result=await api.get('/models');setProvider(result.data);setChecked(new Date())}
  catch {setProviderError('Provider check failed. No current model availability can be confirmed.')}
  finally {setChecking(false)}
 }
 return <section className="health-panel" aria-label="Computers and models health">
  <div className="section-heading"><div><h3>Computers & models</h3>
    <p className="muted">Measured host capacity, signed computer reports and configured model connections—not a prediction of how quickly Kingdom will work.</p>
   </div><button type="button" onClick={()=>Promise.all([hardware.refresh(),cluster.refresh(),profiles.refresh()])}>Refresh health</button></div>
  {statusError && <p role="alert">Current health information is unavailable; any previous values may be stale.</p>}
  {!view ? <p role="status">Waiting for a complete current health report.</p> : <>
    <div className="home-summary-grid">
      <Value label="CPU cores on this host" value={view.cpuCores}/>
      <Value label="Available host RAM" value={view.availableRamGB} unit=" GiB" note="Whole computer, not Kingdom's RAM usage"/>
      <Value label="Free disk on this host" value={view.diskFreeGB} unit=" GiB"/>
      <Value label="Current remote computer reports" value={view.connectedPeers} note={view.pairedPeers===null?'Paired total unavailable':`${view.pairedPeers} paired peers recorded`}/>
      <Value label="Configured AI profiles" value={view.configuredModels} note="Configured is not the same as responding"/>
    </div>
    {view.inventoryComplete===false && <p role="status">Some paired computer inventories are missing or stale. Their health cannot be assumed.</p>}
  </>}
  <h4>Check model-provider connection</h4>
  <p className="muted">This is a read-only provider health check, not a generation request. It does not test every saved model profile.</p>
  <button type="button" onClick={checkProviders} disabled={checking}>{checking?'Checking…':'Check configured providers'}</button>
  {providerError&&<p role="alert">{providerError}</p>}
  {provider&&<div className="health-provider-status" role="status">
    <p>Checked {checked?.toLocaleTimeString()||'time unknown'}.</p>
    <p>Ollama: {provider?.ollama?.available===true?'Responding':provider?.ollama?.available===false?'Not responding':'Unknown'}.</p>
    <p>OpenAI-compatible endpoint: {provider?.openai_compatible?.configured===true?'Configured (not connectivity-tested)':provider?.openai_compatible?.configured===false?'Not configured':'Unknown'}.</p>
    <p className="muted">Individual model readiness, model-specific latency and GPU/RAM use have not been measured by this check.</p>
  </div>}
 </section>
}

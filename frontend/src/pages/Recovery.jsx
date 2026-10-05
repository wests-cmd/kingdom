import React,{useEffect,useRef,useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function Recovery(){
 const {data,error,refresh}=useLiveData('/recovery/status',5000)
 const [plan,setPlan]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const planHeading=useRef(null)
 useEffect(()=>{if(plan)planHeading.current?.focus()},[plan?.plan_id,plan?.state])
 async function action(work){setBusy(true);setMessage('');try{await work();await refresh()}catch{setMessage('The action could not be completed. Check connection, owner access and plan expiry.')}finally{setBusy(false)}}
 return <div className="page-stack"><h1>Recovery</h1>
 {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
 <section className="panel"><h2>Current status</h2><p>Commander: {data?data.ready?'Ready':'Not ready':'Loading'}</p><p>Task processing: {data?data.runtime_running?'Running':'Stopped':'Loading'}</p><p>{data?.notice}</p>
 <button disabled={busy||!data} onClick={()=>action(async()=>{const response=await api.post('/recovery/plans',{action:'restart_runtime'});setPlan(response.data)})}>Review a runtime restart</button></section>
 {plan&&<section className="panel" aria-labelledby="repair-plan-title"><h2 id="repair-plan-title" tabIndex={-1} ref={planHeading}>{plan.summary}</h2><p>{plan.effect}</p><p>Approval expires: {new Date(plan.expires_at*1000).toLocaleTimeString()}. Expiry denies the action.</p><button disabled={busy||plan.state!=='pending'} onClick={()=>action(async()=>{const response=await api.post(`/recovery/plans/${plan.plan_id}/execute`,{approved:true});setPlan(response.data);setMessage(response.data.state==='verified'?'Runtime restart verified.':response.data.error)})}>Approve runtime restart</button><button disabled={busy} onClick={()=>setPlan(null)}>Dismiss without running</button></section>}
 <section className="panel"><h2>Recent recovery activity</h2>{data?.repairs.length?data.repairs.map(item=><div className="record-detail" key={item.plan_id}><strong>{item.summary}</strong><p>Status: {item.state}. {item.error}</p></div>):<p>No recorded repair plans.</p>}</section>
 </div>
}

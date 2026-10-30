import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function ChatGPTHelp(){
 const {data:connection,refresh:refreshConnection}=useLiveData('/chatgpt-plan',600000)
 const {data:help,refresh:refreshHelp}=useLiveData('/assistance',600000)
 const [message,setMessage]=useState(''),[url,setUrl]=useState(''),[models,setModels]=useState([]),[model,setModel]=useState(''),[busy,setBusy]=useState(false)
 const refresh=()=>{refreshConnection();refreshHelp()}
 const act=async fn=>{setBusy(true);setMessage('');try{await fn();refresh()}catch(e){setMessage(e.response?.data?.detail||'Connection or saved work needs attention.')}finally{setBusy(false)}}
 const start=()=>act(async()=>{const {data}=await api.post('/chatgpt-plan/begin',{});setUrl(data.authorization_url);setMessage(data.notice)})
 const choose=()=>act(async()=>{const {data}=await api.get('/chatgpt-plan/models');const choices=data.filter(m=>!m.slug.toLowerCase().includes('codex'));setModels(choices);setModel(choices[0]?.slug||'')})
 const enable=()=>act(async()=>{await api.post('/chatgpt-plan/settings',{enabled:true,model});setMessage('ChatGPT advice connected. Enable backlog help separately below.')})
 const toggle=()=>act(async()=>{await api.post('/assistance/settings',{enabled:!help.settings.enabled,max_daily_calls:help.settings.max_daily_calls,expected_revision:help.settings.revision})})
 const disconnect=()=>act(async()=>{const {data}=await api.post('/chatgpt-plan/sign-out',{});setUrl('');setModels([]);setMessage(data.notice||'ChatGPT disconnected. Saved questions and evidence remain local.')})
 const download=project=>act(async()=>{const {data}=await api.get(`/assistance/training/${encodeURIComponent(project)}`,{responseType:'blob'});const address=URL.createObjectURL(data);const link=document.createElement('a');link.href=address;link.download=`${project}-verified-lessons.jsonl`;link.click();setTimeout(()=>URL.revokeObjectURL(address),1000)})
 return <section aria-label="ChatGPT planning help"><h2>Planning help and local learning</h2>
  <p>Use verified local lessons first. Ask your connected ChatGPT account when help is needed. Answers still require the normal plan review and tests.</p>
  <p>Connection: {connection?.state||'Unavailable'} · Backlog help: {help?.settings?.enabled?'Enabled':'Off'}</p>
  <p>Sign in on the computer that owns this connection. If viewing another Knight, open Kingdom on that Knight to connect its account.</p>
  <button disabled={busy} onClick={start}>Continue with ChatGPT</button>{' '}
  <button disabled={busy} onClick={refresh}>Refresh connection</button>{' '}
  <button disabled={busy} onClick={choose}>Load my models</button>
  {' '}<button disabled={busy||!connection?.active_account} onClick={disconnect}>Disconnect ChatGPT</button>
  {url&&<p><a href={url} target="_blank" rel="noopener noreferrer">Open ChatGPT sign-in on this Knight</a></p>}
  {models.length>0&&<p><label>Planning model <select value={model} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m.slug} value={m.slug}>{m.display_name||m.slug}</option>)}</select></label>{' '}<button disabled={busy||!model} onClick={enable}>Use for advice</button></p>}
  {help?.settings&&<p><button disabled={busy} onClick={toggle}>{help.settings.enabled?'Pause':'Enable'} backlog help</button> · Maximum {help.settings.max_daily_calls} cloud help calls per day. No automatic paid API fallback.</p>}
  {message&&<p role="status">{message}</p>}
  <details><summary>Saved questions and outcomes ({help?.requests?.length||0})</summary>
   {(help?.requests||[]).map(r=><details key={r.id}><summary>{r.project}: {r.kind} — {r.status}</summary><p>{r.question}</p><p>{r.answer||'Waiting for a completed answer.'}</p><p>{r.verification?'Bound acceptance checked':'Unverified advice'} · {r.training_selected?'Selected for training export':'Not selected for training'}</p>{['queued','claimed','sending'].includes(r.status)&&<button disabled={busy} onClick={()=>act(()=>api.post(`/assistance/requests/${encodeURIComponent(r.id)}/cancel`))}>Cancel this question</button>}{r.verification&&<label><input type="checkbox" disabled={busy} checked={r.training_selected} onChange={e=>{const selected=e.target.checked;act(()=>api.post(`/assistance/requests/${encodeURIComponent(r.id)}/training`,{selected}))}}/> Include in local training export</label>}</details>)}
   {[...new Set((help?.requests||[]).filter(r=>r.training_selected).map(r=>r.project))].map(project=><p key={project}><button disabled={busy} onClick={()=>download(project)}>Download selected {project} lessons</button></p>)}
  </details><p>Saving examples does not train a model. Only explicitly selected, currently verified examples enter the local training export.</p>
 </section>
}

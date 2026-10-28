import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {modelComputer} from './ComputerIdentity'
export default function ModelProfiles(){
 const {data:hierarchy}=useLiveData('/hierarchy',10000)
 const {data,error,refresh}=useLiveData('/workspace/model-profiles',10000)
 const [form,setForm]=useState({id:'',provider:'ollama',endpoint:'http://127.0.0.1:11434',model:'',variant:'standard',vision:false,context_characters:24000,pool_group:'',max_parallel:1,timeout_seconds:120,max_output_tokens:2048,num_ctx:8192,api_key:''})
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const change=(key,value)=>setForm(old=>({...old,[key]:value}))
 const save=async event=>{event.preventDefault();setBusy(true);setMessage('')
  try{const {id,...body}=form;await api.put(`/workspace/model-profiles/${encodeURIComponent(id)}`,{...body,api_key:body.api_key||null});setForm(old=>({...old,api_key:''}));setMessage('Model connection saved. Test it before use.');refresh()}
  catch(e){setMessage(e.response?.data?.detail||'Could not save model connection.')}finally{setBusy(false)}}
 const test=async id=>{setBusy(true);try{const {data}=await api.post(`/workspace/model-profiles/${encodeURIComponent(id)}/test`);setMessage(`Connected to ${data.model}: ${data.response}`)}catch(e){setMessage(e.response?.data?.detail||'Model test failed.')}finally{setBusy(false)}}
 return <section className="panel" style={{minWidth:0,overflowWrap:"anywhere"}}><h2>Your model connections</h2><p>{data?.notice}</p><p>Add a connection for each computer. Give trusted computers the same pool name to send simultaneous chats to available computers. Each computer runs its own complete model. Remote addresses need HTTPS, or a local port forwarded over SSH.</p>{error&&<p role="alert">{error}</p>}
  {(data?.capacity||[]).map(item=><p key={item.profile}>{item.profile}: {item.active}/{item.max_parallel} inference slots in use{item.pool?` · pool ${item.pool}`:''}</p>)}
  {(data?.profiles||[]).map(profile=><div className="record-detail" key={profile.id}><h3>{profile.id}</h3><p>{modelComputer(profile,hierarchy)}</p><p>Model server: {profile.endpoint}</p><p>{profile.model} · {profile.variant.replaceAll('_',' ')} · {profile.vision?'Vision enabled':'Text model'} · {profile.has_credentials?'Credential stored':'No credential stored'}</p><button disabled={busy} onClick={()=>test(profile.id)}>Test connection</button><button onClick={()=>setForm({...profile,api_key:''})}>Edit connection</button></div>)}
  <form onSubmit={save} className="appearance-fields">
   <label>Connection name<input required pattern="[a-z][a-z0-9_-]{0,63}" value={form.id} onChange={e=>change('id',e.target.value)} placeholder="my-local-coder"/></label>
   <label>Protocol<select value={form.provider} onChange={e=>change('provider',e.target.value)}><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible server</option></select></label>
   <label>Server address<input required type="url" value={form.endpoint} onChange={e=>change('endpoint',e.target.value)} placeholder="https://provider.example/v1"/></label>
   <details><summary>Private server certificate</summary><label>Trusted CA certificate (PEM, optional)<textarea value={form.ca_certificate||''} onChange={e=>change('ca_certificate',e.target.value)} placeholder="Leave blank for a publicly trusted HTTPS certificate"/></label></details>
   <label>Installed model name<input required value={form.model} onChange={e=>change('model',e.target.value)} placeholder="Your exact model identifier"/></label>
   <label>Model type<select value={form.variant} onChange={e=>change('variant',e.target.value)}><option value="standard">Standard</option><option value="fine_tuned">Fine-tuned</option><option value="abliterated">Abliterated</option><option value="custom">Custom</option></select></label>
   <label>Context character budget<input type="number" min={4000} max={400000} value={form.context_characters} onChange={e=>change('context_characters',Number(e.target.value))}/></label>
   <label>Model hosting<select value={form.hosting||'auto'} onChange={e=>change('hosting',e.target.value)}><option value="auto">Automatic (only loopback Ollama is local)</option><option value="local">Local model on my trusted computers</option><option value="cloud">Cloud provider</option></select></label>
   <label>Computer pool (optional)<input value={form.pool_group||''} pattern="[a-z][a-z0-9_-]{0,63}" onChange={e=>change('pool_group',e.target.value)} placeholder="chat"/></label>
   <label>Computer / Knight ID (optional)<input value={form.computer_id||''} pattern="[A-Za-z][A-Za-z0-9_-]{0,63}" onChange={e=>change('computer_id',e.target.value)} placeholder="Exact paired Knight ID or your computer label"/></label>
   <label>Simultaneous requests on this computer<input type="number" min={1} max={4} value={form.max_parallel||1} onChange={e=>change('max_parallel',Number(e.target.value))}/></label>
   <label>Model timeout in seconds<input type="number" min={30} max={600} value={form.timeout_seconds||120} onChange={e=>change('timeout_seconds',Number(e.target.value))}/></label>
   <label>Maximum reply tokens<input type="number" min={16} max={8192} value={form.max_output_tokens||2048} onChange={e=>change('max_output_tokens',Number(e.target.value))}/></label>
   <label>Ollama context tokens<input type="number" min={512} max={131072} value={form.num_ctx||8192} onChange={e=>change('num_ctx',Number(e.target.value))}/></label>
   <label>API key (optional for local Ollama)<input type="password" autoComplete="off" value={form.api_key} onChange={e=>change('api_key',e.target.value)} placeholder="Blank keeps the saved credential"/></label>
   <label><input type="checkbox" checked={!!form.supports_tools} onChange={e=>change('supports_tools',e.target.checked)}/>This model supports tool calls (required for automatic agent selection)</label><label><input type="checkbox" checked={!!form.disabled} onChange={e=>change('disabled',e.target.checked)}/>Exclude this connection from automatic selection</label><label><input type="checkbox" checked={form.vision} onChange={e=>change('vision',e.target.checked)}/>This model supports images</label>
   <button disabled={busy}>Save model connection</button>
  </form><p className="muted">Credentials are encrypted locally and never returned. Model type is your label, not a promise of capability. Install or train weights with the provider; Kingdom connects to them afterward.</p>{message&&<p role="status">{message}</p>}
 </section>
}

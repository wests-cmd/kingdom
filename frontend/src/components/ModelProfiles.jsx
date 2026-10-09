import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
export default function ModelProfiles(){
 const {data,error,refresh}=useLiveData('/workspace/model-profiles',10000)
 const [form,setForm]=useState({id:'',provider:'ollama',endpoint:'http://127.0.0.1:11434',model:'',variant:'standard',vision:false,context_characters:24000,api_key:''})
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const change=(key,value)=>setForm(old=>({...old,[key]:value}))
 const save=async event=>{event.preventDefault();setBusy(true);setMessage('')
  try{const {id,...body}=form;await api.put(`/workspace/model-profiles/${encodeURIComponent(id)}`,{...body,api_key:body.api_key||null});setForm(old=>({...old,api_key:''}));setMessage('Model connection saved. Test it before use.');refresh()}
  catch(e){setMessage(e.response?.data?.detail||'Could not save model connection.')}finally{setBusy(false)}}
 const test=async id=>{setBusy(true);try{const {data}=await api.post(`/workspace/model-profiles/${encodeURIComponent(id)}/test`);setMessage(`Connected to ${data.model}: ${data.response}`)}catch(e){setMessage(e.response?.data?.detail||'Model test failed.')}finally{setBusy(false)}}
 return <section className="panel"><h2>Your model connections</h2><p>{data?.notice}</p>{error&&<p role="alert">{error}</p>}
  {(data?.profiles||[]).map(profile=><div className="record-detail" key={profile.id}><h3>{profile.id}</h3><p>{profile.model} · {profile.variant.replaceAll('_',' ')} · {profile.vision?'Vision enabled':'Text model'} · {profile.has_credentials?'Credential stored':'No credential stored'}</p><button disabled={busy} onClick={()=>test(profile.id)}>Test connection</button><button onClick={()=>setForm({...profile,api_key:''})}>Edit connection</button></div>)}
  <form onSubmit={save} className="appearance-fields">
   <label>Connection name<input required pattern="[a-z][a-z0-9_-]{0,63}" value={form.id} onChange={e=>change('id',e.target.value)} placeholder="my-local-coder"/></label>
   <label>Protocol<select value={form.provider} onChange={e=>change('provider',e.target.value)}><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible server</option></select></label>
   <label>Server address<input required type="url" value={form.endpoint} onChange={e=>change('endpoint',e.target.value)} placeholder="https://provider.example/v1"/></label>
   <label>Installed model name<input required value={form.model} onChange={e=>change('model',e.target.value)} placeholder="Your exact model identifier"/></label>
   <label>Model type<select value={form.variant} onChange={e=>change('variant',e.target.value)}><option value="standard">Standard</option><option value="fine_tuned">Fine-tuned</option><option value="abliterated">Abliterated</option><option value="custom">Custom</option></select></label>
   <label>Context character budget<input type="number" min={4000} max={400000} value={form.context_characters} onChange={e=>change('context_characters',Number(e.target.value))}/></label>
   <label>API key (optional for local Ollama)<input type="password" autoComplete="off" value={form.api_key} onChange={e=>change('api_key',e.target.value)} placeholder="Blank keeps the saved credential"/></label>
   <label><input type="checkbox" checked={form.vision} onChange={e=>change('vision',e.target.checked)}/>This model supports images</label>
   <button disabled={busy}>Save model connection</button>
  </form><p className="muted">Credentials are encrypted locally and never returned. Model type is your label, not a promise of capability. Install or train weights with the provider; Kingdom connects to them afterward.</p>{message&&<p role="status">{message}</p>}
 </section>
}

import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {scrubText} from './common/TaskResult'

const inputStyle = {width:'100%', boxSizing:'border-box'}
const messageFor = error => {
  const detail = error.response?.data?.detail
  return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item=>item.msg).join('; ') : 'The request failed. Check the connection and try again.'
}
const stageNames = {proposed:'Review the staged recipe',reviewed:'Ready to submit build',waiting_build:'Build task pending',built:'Build verified; test next',waiting_test:'Test task pending',ready:'Tests passed; registration needs your decision',registered:'Connection registered',disabled:'Preparation disabled',failed:'Needs review'}

export default function ToolWorkshop(){
 const {data, error, refresh} = useLiveData('/tool-workshop',10000)
 const [form,setForm] = useState({name:'',objective:'',source:'owner-authored',executable:'',filename:'helper.py',content:'import sys\nprint(sys.argv[1])\n'})
 const [advanced,setAdvanced] = useState(''), [busy,setBusy] = useState(''), [notice,setNotice] = useState(''), [failure,setFailure] = useState('')
 const [query,setQuery] = useState(''), [discovery,setDiscovery] = useState(null), [connectionIds,setConnectionIds] = useState({})
 const change = (key,value)=>setForm(previous=>({...previous,[key]:value}))
 const perform = async (key,operation,success) => {setBusy(key);setFailure('');setNotice('');try{await operation();setNotice(success);await refresh()}catch(e){setFailure(messageFor(e))}finally{setBusy('')}}
 const propose = event => {event.preventDefault();perform('propose',()=>{
  const body = advanced.trim() ? JSON.parse(advanced) : {name:form.name,objective:form.objective,source:form.source,files:{[form.filename]:form.content},dependencies:[],build:{argv:[form.executable,'-m','py_compile',form.filename],timeout_seconds:60},test:{argv:[form.executable,form.filename,'workshop-test'],timeout_seconds:60},connection:{name:form.name,kind:'custom-cli',argv:[form.executable,`{staging}/${form.filename}`,'{prompt}'],environment:{},timeout_seconds:120}}
  return api.post('/tool-workshop',body)
 },'Source staged for review. No command has run.')}
 const action = (item,name,body,success)=>perform(item.id,()=>api.post(`/tool-workshop/${encodeURIComponent(item.id)}/${name}`,body),success)
 return <section className="panel" aria-labelledby="workshop-heading">
  <h2 id="workshop-heading">Build a tool</h2><p>Find an existing connection first. If you need a new tool, stage its source, review its exact recipe, then run build and test tasks. Registration is a separate choice.</p>
  <form onSubmit={e=>{e.preventDefault();perform('discover',async()=>{const result=await api.get('/tool-workshop/discover',{params:{query}});setDiscovery(result.data)},'Discovery refreshed.')}}>
   <label>Find a tool<input value={query} maxLength={200} onChange={e=>setQuery(e.target.value)} placeholder="For example, project inspection"/></label><button disabled={!!busy}>Find existing tools</button>
  </form>
  {discovery&&<div role="status"><p>{discovery.connections.length} connections and {discovery.proposals.length} proposals found.</p>{discovery.connections.map(item=><p key={item.id}>{item.name} · {item.kind} · {item.id}</p>)}{discovery.proposals.map(item=><p key={item.id}>{item.name} · {stageNames[item.status]||item.status}</p>)}</div>}
  <details><summary>Prepare a new tool</summary><p>The guided form prepares a Python CLI. Its default example echoes the prompt. Replace the code and use a meaningful test recipe before relying on it.</p>
   <form onSubmit={propose} className="appearance-fields">
    <label>Tool name<input style={inputStyle} value={form.name} required={!advanced.trim()} maxLength={100} onChange={e=>change('name',e.target.value)}/></label>
    <label>What should it do?<textarea style={inputStyle} value={form.objective} required={!advanced.trim()} maxLength={4000} onChange={e=>change('objective',e.target.value)}/></label>
    <label>Source or author<input style={inputStyle} value={form.source} required={!advanced.trim()} maxLength={1000} onChange={e=>change('source',e.target.value)}/></label>
    <label>Installed Python executable, absolute path<input style={inputStyle} value={form.executable} required={!advanced.trim()} onChange={e=>change('executable',e.target.value)} placeholder="Path to your installed Python executable"/></label>
    <label>Source filename<input style={inputStyle} value={form.filename} required={!advanced.trim()} onChange={e=>change('filename',e.target.value)} placeholder="helper.py"/></label>
    <label>Python source<textarea style={inputStyle} rows={7} value={form.content} required={!advanced.trim()} onChange={e=>change('content',e.target.value)}/></label>
    <details><summary>Advanced recipe and pinned dependencies</summary><p>A complete JSON proposal replaces the guided form. Include files, source, exact build/test argument arrays, dependency pins and a harness connection. Commands execute only through existing task approval. Keep credentials out of recipes.</p><label>Complete proposal JSON<textarea style={inputStyle} rows={10} value={advanced} onChange={e=>setAdvanced(e.target.value)} placeholder='{"name":"...","objective":"...","source":"...","files":{},"dependencies":[],"build":{"argv":[]},"test":{"argv":[]},"connection":{"name":"...","argv":[]}}'/></label></details>
    <button disabled={!!busy}>Stage for review</button>
   </form>
  </details>
  {(error||failure)&&<p role="alert">{failure||error}</p>}{notice&&<p role="status">{notice}</p>}
  {(Array.isArray(data)?data:[]).map(item=><article className="record-detail" key={item.id}>
   <h3>{item.name}</h3><p>{item.objective}</p><p><strong>{stageNames[item.status]||item.status}</strong>{item.task_status?` · task ${item.task_status.replaceAll('_',' ')}`:''}</p>
   {item.error&&<p role="alert">{item.error}</p>}{item.notice&&<p>{item.notice}</p>}
   {item.task_id&&<p>Task: <code>{item.task_id}</code>. Review its command and approval in Governance; inspect output in Tasks.</p>}
   <details><summary>Review source hashes and exact commands</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{scrubText(JSON.stringify({source:item.source,cwd:item.cwd,source_files:item.source_files,dependencies:item.dependencies,build:item.build,test:item.test,connection:item.connection,checksum:item.checksum},null,2))}</pre></details>
   {item.evidence?.length>0&&<details><summary>Build and test evidence ({item.evidence.length})</summary>{item.evidence.map(record=><div key={record.task_id}><h4>{record.stage} · exit {record.output?.exit_code}</h4><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{scrubText(record.output?.output||'No process output.')}</pre><p>{record.verification?.scope}</p></div>)}</details>}
   {item.status==='proposed'&&<button disabled={!!busy} onClick={()=>action(item,'review',{checksum:item.checksum},'Recipe review recorded. Existing execution permissions still apply.')}>Approve this recipe for preparation</button>}
   {['reviewed','built','waiting_build','waiting_test'].includes(item.status)&&<button disabled={!!busy} onClick={()=>action(item,'advance',{},'Preparation state refreshed. Check task approvals if waiting.')}>{item.status==='reviewed'?'Submit build task':item.status==='built'?'Submit test task':'Check task evidence'}</button>}
   {item.status==='ready'&&<div><label>New connection name<input pattern="[a-z][a-z0-9_-]{0,63}" value={connectionIds[item.id]||''} onChange={e=>setConnectionIds(old=>({...old,[item.id]:e.target.value}))} placeholder="my-tool"/></label><button disabled={!!busy||!/^[a-z][a-z0-9_-]{0,63}$/.test(connectionIds[item.id]||'')} onClick={()=>action(item,'register',{checksum:item.checksum,connection_id:connectionIds[item.id]},'Connection registered. Jobs still require existing permissions and approval.')}>Register tested connection</button></div>}
   {!['disabled','registered'].includes(item.status)&&<button disabled={!!busy} onClick={()=>action(item,'disable',{},'Preparation disabled. Already running tasks may finish.')}>Disable preparation</button>}
   {item.connection_id&&<p>Registered connection: <code>{item.connection_id}</code>.</p>}
  </article>)}
 </section>
}

import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {scrubText} from './common/TaskResult'

const fieldStyle={width:'100%',boxSizing:'border-box'}
const labels={draft:'Draft: review preparation',hardware_blocked:'Waiting for suitable hardware',preparing:'Preparation task pending',awaiting_evaluation:'Artifact verified; evaluation needed',evaluating:'Evaluation task pending',evaluated:'Evaluation passed; candidate review needed',promoted:'Approved candidate',withdrawn:'Candidate withdrawn'}
function failureText(error){const detail=error.response?.data?.detail;return typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>item.msg).join('; '):error instanceof SyntaxError?'Enter valid JSON argument and dataset arrays.':'Could not complete this request. Check the connection.'}

export default function ModelLab(){
 const {data,error,refresh}=useLiveData('/model-lab',15000)
 const [form,setForm]=useState({operation:'heretic',base_model:'',output_path:'',executable:'',rollback_model_profile:'',ram_gb:16,vram_gb:8,disk_gb:20,timeout_seconds:1800,downloads_authorized:false})
 const [args,setArgs]=useState('[]'),[datasets,setDatasets]=useState('[]'),[busy,setBusy]=useState(''),[notice,setNotice]=useState(''),[failure,setFailure]=useState(''),[evaluations,setEvaluations]=useState({})
 const change=(key,value)=>setForm(old=>({...old,[key]:value}))
 const perform=async(key,operation,message)=>{setBusy(key);setFailure('');setNotice('');try{await operation();setNotice(message);await refresh()}catch(e){setFailure(failureText(e))}finally{setBusy('')}}
 const action=(job,name,body,message)=>perform(job.id,()=>api.post(`/model-lab/${encodeURIComponent(job.id)}/${name}`,body),message)
 const create=e=>{e.preventDefault();perform('create',()=>{const {ram_gb,vram_gb,disk_gb,...request}=form;return api.post('/model-lab',{...request,executable:form.executable||data?.heretic_executable||'',argv:JSON.parse(args),datasets:JSON.parse(datasets),hardware:{ram_gb,vram_gb,disk_gb}})},'Preparation draft saved. No model has been downloaded, trained or replaced.')}
 const evaluationField=(id,key,value)=>setEvaluations(old=>({...old,[id]:{...old[id],[key]:value}}))
 const evaluate=(job,event)=>{event.preventDefault();perform(job.id,()=>api.post(`/model-lab/${encodeURIComponent(job.id)}/evaluate`,{argv:JSON.parse(evaluations[job.id]?.argv||'[]'),report_path:evaluations[job.id]?.report_path||''}),'Evaluation task submitted for existing permissions and command approval.')}
 return <section className="panel" aria-labelledby="model-lab-heading">
  <h2 id="model-lab-heading">Prepare a model</h2><p>Keep the original model and create a separate candidate. Preparation, evaluation and candidate approval each have their own evidence and owner decision.</p>
  {data?.hardware&&<p>Available now: {data.hardware.ram_gb} GB RAM · {data.hardware.vram_gb} GB GPU memory · {data.hardware.disk_gb} GB workspace disk. {data.hardware.gpu_probe}</p>}
  {data?.notice&&<p>{data.notice}</p>}
  <details><summary>Create a preparation draft</summary><form className="appearance-fields" onSubmit={create}>
   <label>Preparation method<select value={form.operation} onChange={e=>change('operation',e.target.value)}><option value="heretic">Heretic model transformation</option><option value="fine_tune">Fine-tune with a local trainer</option><option value="custom">Custom local preparation</option></select></label>
   <label>Base model identifier or installed model path<input style={fieldStyle} required value={form.base_model} maxLength={300} onChange={e=>change('base_model',e.target.value)} placeholder="Your selected base model"/></label>
   <label>New output folder within Kingdom workspace<input style={fieldStyle} required value={form.output_path} maxLength={300} onChange={e=>change('output_path',e.target.value)} placeholder="models/my-candidate-v1"/></label>
   <label>Installed preparation executable, absolute path<input style={fieldStyle} required={!data?.heretic_executable||form.operation!=='heretic'} value={form.executable} onChange={e=>change('executable',e.target.value)} placeholder={form.operation==='heretic'&&data?.heretic_executable?data.heretic_executable:'Select an installed executable path'}/></label>
   <label>Existing model profile to retain for rollback<input style={fieldStyle} required value={form.rollback_model_profile} maxLength={100} onChange={e=>change('rollback_model_profile',e.target.value)} placeholder="my-current-model"/></label>
   <details open={form.operation!=='heretic'}><summary>Trainer arguments and dataset provenance</summary><p>For custom preparation or fine-tuning, enter arguments as a JSON array with standalone <code>{'{base_model}'}</code> and <code>{'{output}'}</code> placeholders. Fine-tuning needs dataset provenance. Heretic uses its built-in command recipe.</p>
    <label>Trainer arguments JSON<textarea style={fieldStyle} rows={3} value={args} onChange={e=>setArgs(e.target.value)} placeholder='["--model","{base_model}","--output","{output}"]'/></label>
    <label>Dataset provenance JSON<textarea style={fieldStyle} rows={4} value={datasets} onChange={e=>setDatasets(e.target.value)} placeholder='[{"source":"...","revision":"...","sha256":"64 lowercase hex characters","path":"datasets/example.jsonl"}]'/></label>
   </details>
   <details><summary>Hardware and execution budgets</summary><p>Set the real requirements of your selected model and trainer. Kingdom checks free resources before dispatch.</p>
    <label>Required free RAM (GB)<input type="number" min={1} max={4096} step="0.1" value={form.ram_gb} onChange={e=>change('ram_gb',Number(e.target.value))}/></label>
    <label>Required free GPU memory (GB)<input type="number" min={0} max={1024} step="0.1" value={form.vram_gb} onChange={e=>change('vram_gb',Number(e.target.value))}/></label>
    <label>Required free disk (GB)<input type="number" min={1} max={10000} step="0.1" value={form.disk_gb} onChange={e=>change('disk_gb',Number(e.target.value))}/></label>
    <label>Process time limit (seconds)<input type="number" min={30} max={1800} value={form.timeout_seconds} onChange={e=>change('timeout_seconds',Number(e.target.value))}/></label>
   </details>
   <label><input type="checkbox" checked={form.downloads_authorized} onChange={e=>change('downloads_authorized',e.target.checked)}/> I authorize possible model and dataset downloads for this preparation. Execution still needs task approval.</label>
   <button disabled={!!busy}>Save preparation draft</button>
  </form></details>
  {(error||failure)&&<p role="alert">{failure||error}</p>}{notice&&<p role="status">{notice}</p>}
  {(data?.jobs||[]).map(job=><article className="record-detail" key={job.id}>
   <h3>{job.request.base_model}</h3><p><strong>{labels[job.status]||job.status}</strong> · {job.request.operation.replaceAll('_',' ')}</p><p>Output: <code>{job.request.output_path}</code></p>
   {job.missing_hardware?.length>0&&<p role="alert">Insufficient free resources: {job.missing_hardware.map(name=>name.replaceAll('_',' ')).join(', ')}. This job has not started.</p>}
   {job.error&&<p role="alert">{job.error}</p>}{job.notice&&<p>{job.notice}</p>}
   {job.preparation_task_id&&<p>Preparation task: <code>{job.preparation_task_id}</code>. Review command approvals in Governance and actual process output in Tasks.</p>}
   {job.evaluation_task_id&&<p>Evaluation task: <code>{job.evaluation_task_id}</code>.</p>}
   <details><summary>Exact command, provenance and retained evidence</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{scrubText(JSON.stringify({argv:job.argv,request:job.request,hardware_snapshot:job.hardware_snapshot,artifact:job.artifact,evaluation:job.evaluation},null,2))}</pre></details>
   {['draft','hardware_blocked'].includes(job.status)&&<button disabled={!!busy} onClick={()=>action(job,'start',{},'Readiness checked. If dispatched, approve the exact command in Governance.')}>Check hardware and submit preparation</button>}
   {['preparing','evaluating'].includes(job.status)&&<button disabled={!!busy} onClick={()=>action(job,'refresh',{},'Retained task and artifact evidence checked.')}>Check task and artifact evidence</button>}
   {job.status==='awaiting_evaluation'&&<details><summary>Submit a meaningful evaluation</summary><p>The evaluator must write a new JSON report with <code>passed: true</code>, the matching <code>base_model</code>, <code>artifact_sha256</code> and nonempty <code>metrics</code>. A process exit alone cannot approve the candidate.</p><p>Artifact SHA256: <code style={{overflowWrap:'anywhere'}}>{job.artifact?.sha256}</code></p><form onSubmit={event=>evaluate(job,event)}>
    <label>Exact evaluator argv JSON<textarea style={fieldStyle} required rows={3} value={evaluations[job.id]?.argv||''} onChange={e=>evaluationField(job.id,'argv',e.target.value)} placeholder='["/absolute/path/to/evaluator","..."]'/></label>
    <label>New report path within workspace<input style={fieldStyle} required value={evaluations[job.id]?.report_path||''} onChange={e=>evaluationField(job.id,'report_path',e.target.value)} placeholder="evaluations/candidate-v1.json"/></label><button disabled={!!busy}>Submit evaluation task</button>
   </form></details>}
   {job.status==='evaluated'&&<button disabled={!!busy} onClick={()=>action(job,'promote',{},'Candidate approved in the registry. Serving model connections remain unchanged.')}>Approve evaluated candidate</button>}
   {job.promotion_scope&&<p>{job.promotion_scope}</p>}
   {job.status==='promoted'&&<button disabled={!!busy} onClick={()=>action(job,'rollback',{},'Candidate withdrawn. Existing serving model connections were not changed.')}>Withdraw candidate</button>}
   {job.rollback_scope&&<p>{job.rollback_scope}</p>}
  </article>)}
 </section>
}

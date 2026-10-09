import React, { useState, useEffect } from "react"

import api from "../api"

import useLiveData from "../hooks/useLiveData"

import TaskResult, {DebugDetails, scrubText} from '../components/common/TaskResult'

import {workerLabel} from '../components/common/presentation'
import MissionEditor from '../components/MissionEditor'
import DesktopActions from '../components/DesktopActions'

export default function Tasks() {

  const {data: taskData, error: loadError, refresh: loadTasks} = useLiveData("/tasks", 3000)

  const tasks = taskData || []

  const [taskMode, setTaskMode] = useState("mission")

  const [inputData, setInputData] = useState("")

  const [error, setError] = useState("")

  const [submitting, setSubmitting] = useState(false)

  const [developerView,setDeveloperView] = useState(false)

  const [attachments,setAttachments] = useState([]), [profiles,setProfiles] = useState([]), [modelProfile,setModelProfile] = useState('')

  const [offload,setOffload] = useState(false), [mission,setMission] = useState(null), [planText,setPlanText] = useState('')

  const {data:missions,refresh:refreshMissions} = useLiveData('/missions',4000)

  useEffect(()=>{api.get('/workspace/model-profiles').then(r=>setProfiles(r.data.profiles)).catch(()=>{})},[])

  const upload = async event => {

    setSubmitting(true);setError('')

    try {

      const files = [...event.target.files]
      if(files.length) setTaskMode('mission')

      if(files.length + attachments.length > 20) throw new Error('Use at most 20 attachments.')

      for(const file of files) {

        if(file.size > 20*1024*1024) throw new Error(`${file.name} exceeds 20 MB.`)

        const {data} = await api.post(`/workspace/attachments?filename=${encodeURIComponent(file.name)}`,file,{headers:{'Content-Type':'application/octet-stream'}})

        setAttachments(old=>old.some(item=>item.id===data.id)?old:[...old,data])

      }

    } catch(e) {setError(e.response?.data?.detail || e.message || 'Upload failed.')} finally {setSubmitting(false);event.target.value=''}

  }

  const draftMission = async () => {

    if(!inputData.trim()) {setError('Describe what you want built first.');return}

    setSubmitting(true);setError('')

    try {const {data}=await api.post('/missions/plan',{objective:inputData,attachment_ids:attachments.map(item=>item.id),model_profile:modelProfile||null,offload_analysis:offload});setMission(data);setPlanText(JSON.stringify(data.plan,null,2));refreshMissions()}

    catch(e) {setError(e.response?.data?.detail || 'Mission planning failed.')} finally {setSubmitting(false)}

  }

  const missionAction = async (item,action) => {

    setError('');setSubmitting(true)

    try {await api.post(`/missions/${item.id}/${action}`,action==='approve'?{version:item.version}:{});if(action==='approve'){await api.post('/start');await api.post(`/missions/${item.id}/advance`)} refreshMissions()}

    catch(e){setError(e.response?.data?.detail||'Mission action failed.')}finally{setSubmitting(false)}

  }

  const savePlan = async () => {

    try {const {data}=await api.put(`/missions/${mission.id}`,{version:mission.version,plan:JSON.parse(planText)});setMission(data);refreshMissions()}

    catch(e){setError(e.response?.data?.detail||'Check the edited plan format.')}

  }

  const handleCreateTask = async (e) => {

    e.preventDefault()
    if(taskMode==='mission'){await draftMission();return}

    if (!inputData.trim()) { setError("Enter a task description before submitting."); return }

    setSubmitting(true)

    setError("")

    try {

      await api.post("/tasks", { prompt: inputData.trim(), metadata: { type: "user_task", attachment_ids:attachments.map(item=>item.id), model_profile:modelProfile||null, offload, ...(taskMode ? { tool: taskMode } : {}) } })

      setInputData("")

      setAttachments([])

      loadTasks()

    } catch (err) {

      const detail = err.response?.data?.detail

      setError(typeof detail === "string" ? detail : Array.isArray(detail)

        ? detail.map(item => item.msg).join("; ") : "Task could not be submitted. Please try again.")

    } finally { setSubmitting(false) }

  }

  const handleCancelTask = async (id) => {

    try { await api.post(`/tasks/${id}/cancel`); loadTasks() }

    catch (err) { setError(err.response?.data?.detail || "Task could not be cancelled.") }

  }

  return (

    <div>

      <h2>Task Management</h2>

      <p className="muted" style={{marginBottom:20}}>Submit work, inspect verified results, or cancel tasks that have not started.</p>

      {loadError && <p role="alert">{loadError}</p>}

      <form className="task-form" onSubmit={handleCreateTask} style={{ marginBottom: "24px" }}>

        <label>Task <select value={taskMode} onChange={e => setTaskMode(e.target.value)}><option value="mission">Build a complete mission (review first)</option><option value="text.analyze@1.0.0">Analyze text</option><option value="code.python.analyze@1.0.0">Check Python syntax</option><option value="">Ask your configured AI</option></select></label>

        <textarea

          aria-label="Task description"

          rows={12}

          maxLength={500000}

          placeholder="New task description..."

          value={inputData}

          onChange={e => setInputData(e.target.value)}

          style={{ padding: "16px", width: "100%", minHeight: "260px", resize:"vertical", margin:"16px 0" }}

        />

        <p className="muted">Up to 500,000 characters. Add source code, ZIP, PDF, images, text, JSON or CSV (20 files, 20 MB each). Uploaded files are data; they never grant execution permission.</p>

        <label>Attachments <input type="file" multiple accept=".zip,.pdf,.jpg,.jpeg,.png,.webp,.txt,.md,.py,.js,.jsx,.ts,.tsx,.json,.yaml,.yml,.csv,.log,.html,.css,.xml,.toml,.ini,.sql,.sh,.ps1" onChange={upload} disabled={submitting}/></label>

        {attachments.map(item=><p key={item.id}>{item.filename} · {Math.round(item.bytes/1024)} KB · stored {Math.round(item.stored_bytes/1024)} KB <button type="button" onClick={()=>setAttachments(old=>old.filter(x=>x.id!==item.id))}>Remove from task</button>{item.kind==='image' && ' · Select a vision model to inspect its contents.'}{item.kind==='pdf'&&!item.text_extracted&&' · No text detected; OCR has not been performed.'}</p>)}

        <label>Model <select value={modelProfile} onChange={e=>setModelProfile(e.target.value)}><option value="">Installation default</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}{p.vision?' · vision':''}</option>)}</select></label>

        <label><input type="checkbox" checked={offload} onChange={e=>setOffload(e.target.checked)}/>At level 5, offload supported analysis to a healthy paired computer</label>

        <div className="action-row"><button type="button" disabled={submitting} onClick={draftMission}>Plan a complete mission</button><button type="submit" disabled={submitting} style={{ padding: "8px 16px" }}>{submitting ? "Submitting…" : taskMode==='mission'?"Review mission plan":"Submit Task"}</button></div>

      </form>

      {error && <p role="alert">{error}</p>}
      <DesktopActions onQueued={loadTasks}/>

      {mission && <section className="panel"><h3>Review and edit the mission</h3><p>Add or remove steps, requirements and deliverables before approving. No plan executes just because it was generated.</p><MissionEditor value={planText} onChange={setPlanText}/><details><summary>Advanced plan format</summary><textarea aria-label="Mission plan" rows={16} style={{width:'100%',minHeight:300}} value={planText} onChange={e=>setPlanText(e.target.value)}/></details><button disabled={submitting} onClick={savePlan}>Save edited plan</button></section>}

      <section><h3>Missions</h3>{(missions||[]).map(item=><article className="task-record" key={item.id}><h4>{item.plan.title}</h4><p>{item.status.replaceAll('_',' ')} · revision {item.version}</p><p>Deliverables: {item.plan.deliverables.join('; ')}</p>{item.plan.missing_requirements.map((r,i)=><p role="status" key={i}>Needed: {r}</p>)}<ol>{item.plan.steps.map(step=><li key={step.id}>{step.title} · {step.kind} · {item.steps[step.id]?.status||'not started'}<small> — {step.acceptance}</small></li>)}</ol>{item.failure&&<p role="alert">{item.failure}</p>}{item.status==='draft'&&<button disabled={submitting||item.plan.missing_requirements.length>0} onClick={()=>missionAction(item,'approve')}>Approve this plan and start</button>}{['approved','running'].includes(item.status)&&<><button disabled={submitting} onClick={()=>missionAction(item,'advance')}>Continue next ready step</button><button disabled={submitting} onClick={()=>missionAction(item,'cancel')}>Cancel mission</button></>}{item.report?.length>0&&<details><summary>Completion report and why</summary>{item.report.map(r=><p key={r.task_id}>{r.step}: {r.why} · evidence task {r.task_id}</p>)}</details>}</article>)}</section>

      <h4>Active & Historical Tasks ({tasks.length})</h4>

      <label><input type="checkbox" checked={developerView} onChange={event => setDeveloperView(event.target.checked)}/>Show developer diagnostics for these owner-authorized tasks</label>

      {taskData === null ? <p>Loading tasks…</p> : tasks.length === 0 ? <p style={{ color: "var(--text-muted)" }}>No tasks submitted yet.</p> : (

        <ul style={{ listStyle: "none", padding: 0 }}>

          {tasks.map(t => (

            <li key={t.id} className="task-record">

              <div className="task-meta"><span className="status-chip">{t.status}</span><span>{new Date(t.created_at).toLocaleString()}</span></div>

              <p className="task-input">{t.metadata?.tool === 'provider.metadata@1.0.0' ? 'Reviewed provider metadata test' : t.metadata?.tool === 'code.python.analyze@1.0.0' ? 'Python syntax analysis' : t.metadata?.tool === 'text.analyze@1.0.0' ? 'Text analysis' : 'Configured model task'}</p>

              <details><summary>View supplied input</summary><pre>{scrubText(t.prompt || t.input?.prompt || '').slice(0,10000)}</pre></details>

              {t.error && <p role="alert">This task did not complete. Review its permissions, provider availability and input. Developer diagnostics contain the recorded failure.</p>}

              {t.assigned_knight && <p className="muted">Worker: {workerLabel(t.assigned_knight)}</p>}

              {t.result && <TaskResult result={t.result} taskId={t.id}/>}

              {developerView && <DebugDetails value={{id:t.id,metadata:t.metadata,input:t.input,result:t.result,error:t.error}}/>}

              {['queued','QUEUED','WAITING_APPROVAL'].includes(t.status) && <button onClick={() => handleCancelTask(t.id)} style={{marginTop:12}}>Cancel Task</button>}

            </li>

          ))}

        </ul>

      )}

    </div>

  )

}

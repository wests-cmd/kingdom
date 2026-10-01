import React, { useState, useEffect } from "react"
import api from "../api"
import useLiveData from "../hooks/useLiveData"
import TaskResult, {DebugDetails, scrubText} from '../components/common/TaskResult'
import {workerLabel} from '../components/common/presentation'

export default function Tasks() {
  const {data: taskData, error: loadError, refresh: loadTasks} = useLiveData("/tasks", 3000)
  const tasks = taskData || []
  const [taskMode, setTaskMode] = useState("text.analyze@1.0.0")
  const [inputData, setInputData] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [developerView,setDeveloperView] = useState(false)

  const handleCreateTask = async (e) => {
    e.preventDefault()
    if (!inputData.trim()) { setError("Enter a task description before submitting."); return }
    setSubmitting(true)
    setError("")
    try {
      await api.post("/tasks", { prompt: inputData.trim(), metadata: { type: "user_task", ...(taskMode ? { tool: taskMode } : {}) } })
      setInputData("")
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
        <label>Task <select value={taskMode} onChange={e => setTaskMode(e.target.value)}><option value="text.analyze@1.0.0">Analyze text</option><option value="code.python.analyze@1.0.0">Check Python syntax</option><option value="">Ask your configured AI</option></select></label>
        <input
          type="text"
          placeholder="New task description..."
          value={inputData}
          onChange={e => setInputData(e.target.value)}
          style={{ padding: "8px", width: "320px", marginRight: "8px" }}
        />
        <button type="submit" disabled={submitting} style={{ padding: "8px 16px" }}>{submitting ? "Submitting…" : "Submit Task"}</button>
      </form>
      {error && <p role="alert">{error}</p>}

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
              {t.result && <TaskResult result={t.result}/>}
              {developerView && <DebugDetails value={{id:t.id,metadata:t.metadata,input:t.input,result:t.result,error:t.error}}/>}
              {['queued','QUEUED','WAITING_APPROVAL'].includes(t.status) && <button onClick={() => handleCancelTask(t.id)} style={{marginTop:12}}>Cancel Task</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

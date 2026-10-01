import React, { useState, useEffect } from "react"
import api from "../api"
import useLiveData from "../hooks/useLiveData"

export default function Tasks() {
  const {data: taskData, error: loadError, refresh: loadTasks} = useLiveData("/tasks", 3000)
  const tasks = taskData || []
  const [taskMode, setTaskMode] = useState("text.analyze@1.0.0")
  const [inputData, setInputData] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

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
      {taskData === null ? <p>Loading tasks…</p> : tasks.length === 0 ? <p style={{ color: "#888" }}>No tasks submitted yet.</p> : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {tasks.map(t => (
            <li key={t.id} className="task-record">
              <div className="task-meta"><span className="status-chip">{t.status}</span><span>{new Date(t.created_at).toLocaleString()}</span></div>
              <p className="task-input">{t.prompt || t.input?.prompt || 'Task'}</p>
              {t.error && <p role="alert"><strong>Reason:</strong> {t.error}</p>}
              {t.assigned_knight && <p className="muted">Worker: {t.assigned_knight}</p>}
              {t.result && <details><summary>View execution result</summary><pre>{JSON.stringify(t.result,null,2)}</pre></details>}
              <details><summary className="muted">Task details</summary><pre>{JSON.stringify({id:t.id,metadata:t.metadata,input:t.input},null,2)}</pre></details>
              {['queued','QUEUED','WAITING_APPROVAL'].includes(t.status) && <button onClick={() => handleCancelTask(t.id)} style={{marginTop:12}}>Cancel Task</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

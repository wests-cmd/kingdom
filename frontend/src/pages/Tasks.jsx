import React, { useState, useEffect } from "react"
import api from "../api"

export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [inputData, setInputData] = useState("")

  const loadTasks = () => {
    api.get("/tasks")
      .then(res => setTasks(res.data || []))
      .catch(() => setTasks([]))
  }

  useEffect(() => {
    loadTasks()
    const interval = setInterval(loadTasks, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleCreateTask = async (e) => {
    e.preventDefault()
    if (!inputData.trim()) return
    await api.post("/tasks", { type: "user_task", input: { content: inputData } })
    setInputData("")
    loadTasks()
  }

  const handleCancelTask = async (id) => {
    await api.post(`/tasks/${id}/cancel`)
    loadTasks()
  }

  return (
    <div>
      <h2>Task Management</h2>

      <form onSubmit={handleCreateTask} style={{ marginBottom: "16px" }}>
        <input
          type="text"
          placeholder="New task description..."
          value={inputData}
          onChange={e => setInputData(e.target.value)}
          style={{ padding: "8px", width: "320px", marginRight: "8px" }}
        />
        <button type="submit" style={{ padding: "8px 16px" }}>Submit Task</button>
      </form>

      <h4>Active & Historical Tasks ({tasks.length})</h4>
      {tasks.length === 0 ? <p style={{ color: "#888" }}>No tasks submitted yet.</p> : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {tasks.map(t => (
            <li key={t.id} style={{ background: "#222", padding: "10px", borderRadius: "6px", marginBottom: "8px" }}>
              <div><strong>Task ID:</strong> {t.id}</div>
              <div><strong>Status:</strong> <span style={{ color: t.status === "completed" ? "lightgreen" : t.status === "failed" ? "red" : "orange" }}>{t.status}</span></div>
              <div><strong>Input:</strong> {JSON.stringify(t.input)}</div>
              {t.assigned_knight && <div><strong>Assigned Knight:</strong> {t.assigned_knight}</div>}
              {t.result && <div><strong>Result:</strong> {JSON.stringify(t.result)}</div>}
              {t.status === "queued" || t.status === "running" ? (
                <button onClick={() => handleCancelTask(t.id)} style={{ marginTop: "6px", background: "red", color: "#fff", border: "none", padding: "4px 8px", borderRadius: "4px", cursor: "pointer" }}>
                  Cancel Task
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

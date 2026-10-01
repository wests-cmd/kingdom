import React, { useState, useEffect } from "react"
import api from "../api"
import useLiveData from "../hooks/useLiveData"


export default function Memory() {
  const [query, setQuery] = useState("")
  const [newContent, setNewContent] = useState("")
  const [saveError,setSaveError] = useState("")
  const [saving,setSaving] = useState(false)
  const {data,error,refresh} = useLiveData(query.trim() ? `/memory/search?query=${encodeURIComponent(query)}` : "/memory")
  const memories = data || []
  const handleAdd = async event => {
    event.preventDefault(); if (!newContent.trim()) return
    setSaving(true);setSaveError("")
    try {await api.post("/memory",{content:newContent,metadata:{source:"user",trust:"user-supplied"}});setNewContent("");await refresh()}
    catch(e) {setSaveError(e.response?.data?.detail || "Memory could not be stored.")}
    finally {setSaving(false)}
  }

  return (
    <div>
      <h2>Persistent Memory</h2>
      {(error || saveError) && <p role="alert">{error || saveError}</p>}

      <form onSubmit={handleAdd} style={{ marginBottom: "16px" }}>
        <input
          type="text"
          placeholder="Store new memory..."
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          style={{ padding: "8px", width: "300px", marginRight: "8px" }}
        />
        <button disabled={saving} type="submit" style={{ padding: "8px 16px" }}>Store Memory</button>
      </form>

      <div style={{ marginBottom: "16px" }}>
        <input
          type="text"
          placeholder="Search memory..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{ padding: "6px", width: "250px" }}
        />
      </div>

      <div style={{ marginBottom: "20px" }}>
        <h4>Memory Records ({memories.length})</h4>
        {data === null ? <p>Loading memory…</p> : memories.length === 0 ? <p style={{ color: "#888" }}>No memory records found.</p> : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {memories.map(m => (
              <li key={m.id} style={{ background: "#222", padding: "8px 12px", borderRadius: "4px", marginBottom: "6px" }}>
                <div><strong>{m.content}</strong></div>
                <div style={{ fontSize: "0.8em", color: "#888" }}>Source: {m.metadata?.source || (m.metadata?.task_id ? "task" : "Unspecified")} | Trust: {m.metadata?.trust || "Unspecified"}</div>
              </li>
            ))}
          </ul>
        )}
      </div>


    </div>
  )
}

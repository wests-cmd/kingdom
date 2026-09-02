import React, { useState, useEffect } from "react"
import api from "../api"
import MemoryGraph from "../components/graphs/MemoryGraph"

export default function Memory() {
  const [memories, setMemories] = useState([])
  const [query, setQuery] = useState("")
  const [newContent, setNewContent] = useState("")

  const loadMemories = (q = "") => {
    api.get(`/memory/search?query=${encodeURIComponent(q)}`)
      .then(res => setMemories(res.data || []))
      .catch(() => setMemories([]))
  }

  useEffect(() => {
    loadMemories()
  }, [])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!newContent.trim()) return
    await api.post("/memory", { content: newContent, source: "user" })
    setNewContent("")
    loadMemories(query)
  }

  return (
    <div>
      <h2>Persistent Memory</h2>

      <form onSubmit={handleAdd} style={{ marginBottom: "16px" }}>
        <input
          type="text"
          placeholder="Store new memory..."
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          style={{ padding: "8px", width: "300px", marginRight: "8px" }}
        />
        <button type="submit" style={{ padding: "8px 16px" }}>Store Memory</button>
      </form>

      <div style={{ marginBottom: "16px" }}>
        <input
          type="text"
          placeholder="Search memory..."
          value={query}
          onChange={e => { setQuery(e.target.value); loadMemories(e.target.value); }}
          style={{ padding: "6px", width: "250px" }}
        />
      </div>

      <div style={{ marginBottom: "20px" }}>
        <h4>Memory Records ({memories.length})</h4>
        {memories.length === 0 ? <p style={{ color: "#888" }}>No memory records found.</p> : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {memories.map(m => (
              <li key={m.id} style={{ background: "#222", padding: "8px 12px", borderRadius: "4px", marginBottom: "6px" }}>
                <div><strong>{m.content}</strong></div>
                <div style={{ fontSize: "0.8em", color: "#888" }}>Source: {m.source} | Trust: {m.trust}</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <MemoryGraph />
    </div>
  )
}

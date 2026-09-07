import React, { useState, useEffect } from "react"
import { api } from "../../api"

export default function Sidebar({ currentPage, setCurrentPage }) {
  const [runningVersion, setRunningVersion] = useState("v40.2.0")

  useEffect(() => {
    api.getSystemVersion()
      .then(data => {
        if (data && data.version) {
          setRunningVersion(`v${data.version}`)
        }
      })
      .catch(() => {})
  }, [])
  const navItems = [
    { id: "Dashboard", label: "Dashboard" },
    { id: "Swarm", label: "Swarm" },
    { id: "Runtime", label: "Runtime" },
    { id: "AIMap", label: "AI Map" },
    { id: "Memory", label: "Memory" },
    { id: "Routing", label: "Routing" },
    { id: "Governance", label: "Governance" },
    { id: "Skills", label: "Skills" },
    { id: "Learning", label: "Learning Center" },
    { id: "Nodes", label: "Nodes & Cluster" },
    { id: "Security", label: "Security" },
    { id: "Logs", label: "Logs & Activity" }
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        KINGDOM <span>{runningVersion}</span>
      </div>
      <ul className="sidebar-nav">
        {navItems.map(item => (
          <li
            key={item.id}
            className={`sidebar-item ${currentPage === item.id ? "active" : ""}`}
            onClick={() => setCurrentPage(item.id)}
          >
            {item.label}
          </li>
        ))}
      </ul>
    </aside>
  )
}

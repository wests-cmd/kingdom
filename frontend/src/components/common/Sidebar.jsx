import React from "react"

export default function Sidebar({ currentPage, setCurrentPage }) {
  const navItems = [
    { id: "Dashboard", label: "Dashboard" },
    { id: "Swarm", label: "Swarm" },
    { id: "Runtime", label: "Runtime" },
    { id: "AIMap", label: "AI Map" },
    { id: "Memory", label: "Memory" },
    { id: "Routing", label: "Routing" },
    { id: "Governance", label: "Governance" },
    { id: "Security", label: "Security" },
    { id: "Logs", label: "Logs & Activity" }
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        KINGDOM <span>v40.1</span>
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

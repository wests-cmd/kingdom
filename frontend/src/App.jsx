import React, { useState, useEffect } from "react"
import Sidebar from "./components/common/Sidebar"
import Dashboard from "./pages/Dashboard"
import Swarm from "./pages/Swarm"
import Runtime from "./pages/Runtime"
import AIMap from "./pages/AIMap"
import Memory from "./pages/Memory"
import Routing from "./pages/Routing"
import Governance from "./pages/Governance"
import Settings from "./pages/Settings"
import Logs from "./pages/Logs"
import { realtime } from "./websocket"
import "./styles/app.css"

export default function App() {
  const [currentPage, setCurrentPage] = useState("Dashboard")
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    realtime.connect()
    const unsubscribe = realtime.onStatusChange(status => setIsConnected(status))
    return () => unsubscribe()
  }, [])

  const renderPage = () => {
    switch (currentPage) {
      case "Dashboard": return <Dashboard />
      case "Swarm": return <Swarm />
      case "Runtime": return <Runtime />
      case "AIMap": return <AIMap />
      case "Memory": return <Memory />
      case "Routing": return <Routing />
      case "Governance": return <Governance />
      case "Security": return <Settings />
      case "Logs": return <Logs />
      default: return <Dashboard />
    }
  }

  return (
    <div className="layout">
      <Sidebar currentPage={currentPage} setCurrentPage={setCurrentPage} />

      <div className="main-container">
        <header className="topbar">
          <div className="page-title">{currentPage}</div>
          <div className="status-indicator">
            Connection:{" "}
            <span className={isConnected ? "badge-online" : "badge-offline"}>
              {isConnected ? "ONLINE (REALTIME)" : "DISCONNECTED"}
            </span>
          </div>
        </header>

        {!isConnected && (
          <div style={{ background: "#2a1213", color: "#f87171", borderBottom: "1px solid var(--accent-red)", padding: "8px 24px", fontSize: "12px" }}>
            Warning: Disconnected from Kingdom Commander. Attempting automatic reconnection...
          </div>
        )}

        <main className="content">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

import React, { useState, useEffect } from "react"
import Sidebar from "./components/common/Sidebar"
import Dashboard from "./pages/Dashboard"
import Swarm from "./pages/Swarm"
import Runtime from "./pages/Runtime"
import Tasks from "./pages/Tasks"
import AIMap from "./pages/AIMap"
import Memory from "./pages/Memory"
import Routing from "./pages/Routing"
import Governance from "./pages/Governance"
import Skills from "./pages/Skills"
import Learning from "./pages/Learning"
import { Nodes } from "./pages/Nodes"
import { MobileGateway } from "./pages/MobileGateway"
import Settings from "./pages/Settings"
import Logs from "./pages/Logs"
import { realtime } from "./websocket"
import api from "./api"
import { initializeSession, setAccessCode } from "./session"
import "./styles/app.css"

export default function App() {
  const [currentPage, setCurrentPage] = useState("Dashboard")
  const [isConnected, setIsConnected] = useState(false)
  const [authorized, setAuthorized] = useState(false)
  const [accessCode, setCode] = useState("")
  const [error, setError] = useState("")
  const connect = async () => {
    try { await api.post("/auth/session"); setAuthorized(true); setError("") }
    catch { setError("Enter the owner access code supplied by your Kingdom installation.") }
  }
  useEffect(() => { initializeSession().then(connect).catch(() => setError("Desktop authentication failed.")) }, [])

  useEffect(() => {
    if (!authorized) return
    realtime.connect()
    const unsubscribe = realtime.onStatusChange(status => setIsConnected(status))
    return () => unsubscribe()
  }, [authorized])

  const renderPage = () => {
    switch (currentPage) {
      case "Dashboard": return <Dashboard />
      case "Swarm": return <Swarm />
      case "Runtime": return <Runtime />
      case "Tasks": return <Tasks />
      case "AIMap": return <AIMap />
      case "Memory": return <Memory />
      case "Routing": return <Routing />
      case "Governance": return <Governance />
      case "Skills": return <Skills />
      case "Learning": return <Learning />
      case "Nodes": return <Nodes />
      case "Mobile": return <MobileGateway />
      case "Security": return <Settings />
      case "Logs": return <Logs />
      default: return <Dashboard />
    }
  }

  if (!authorized) return <main className="content"><h1>Connect to Kingdom</h1>
    <p>Desktop access is automatic. For a server, use the owner access code from the server's data/owner-token file or your administrator.</p>
    <form onSubmit={e => { e.preventDefault(); setAccessCode(accessCode); connect() }}>
      <label>Owner access code <input type="password" autoComplete="off" value={accessCode} onChange={e => setCode(e.target.value)} /></label>
      <button type="submit">Connect</button>
    </form>{error && <p role="alert">{error}</p>}</main>
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

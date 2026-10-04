import React, { useState, useEffect } from "react"
import Sidebar from "./components/common/Sidebar"
import Dashboard from "./pages/Dashboard"
import Swarm from "./pages/Swarm"
import Runtime from "./pages/Runtime"
import Tasks from "./pages/Tasks"
import AIMap from "./pages/AIMap"
import SkillMaps from "./pages/SkillMaps"
import Memory from "./pages/Memory"
import Routing from "./pages/Routing"
import Governance from "./pages/Governance"
import Skills from "./pages/Skills"
import Learning from "./pages/Learning"
import { Nodes } from "./pages/Nodes"
import { MobileGateway } from "./pages/MobileGateway"
import Settings from "./pages/Settings"
import AppearanceSettings from './pages/AppearanceSettings'
import AccessibilitySettings from './components/common/AccessibilitySettings'
import AppearanceSync from './components/common/AppearanceSync'
import Recovery from './pages/Recovery'
import {AppearanceProvider} from './components/common/AppearanceProvider'
import Logs from "./pages/Logs"
import ConnectDevice from "./pages/ConnectDevice"
import { realtime } from "./websocket"
import api from "./api"
import { initializeSession, setAccessCode } from "./session"
import "./styles/app.css"

export default function App() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => { const change = () => setHash(window.location.hash); window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  return <AppearanceProvider>{hash.startsWith('#/connect') ? <ConnectDevice /> : <OwnerApp />}</AppearanceProvider>
}

function OwnerApp() {
  const [currentPage, setCurrentPage] = useState("Dashboard")
  const [isConnected, setIsConnected] = useState(false)
  const [authorized, setAuthorized] = useState(false)
  const [accessCode, setCode] = useState("")
  const [error, setError] = useState("")
  useEffect(()=>{if(authorized)document.getElementById('main-content')?.focus()},[currentPage,authorized])
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
      case "SkillMaps": return <SkillMaps />
      case "Memory": return <Memory />
      case "Routing": return <Routing />
      case "Governance": return <Governance />
      case "Skills": return <Skills />
      case "Learning": return <Learning />
      case "Nodes": return <Nodes />
      case "Mobile": return <MobileGateway />
      case "Security": return <Settings />
      case "Settings": return <AppearanceSettings />
      case "Recovery": return <Recovery />
      case "Logs": return <Logs />
      default: return <Dashboard />
    }
  }

  if (!authorized) return <main className="content"><h1>Connect to Kingdom</h1>
    <p>Adding a phone or another device? <a href="/#/connect">Enter a device connection code</a>.</p>
    <p>Desktop access is automatic. For a server, use the owner access code from the server's data/owner-token file or your administrator.</p>
    <form onSubmit={e => { e.preventDefault(); setAccessCode(accessCode); connect() }}>
      <label>Owner access code <input type="password" autoComplete="off" value={accessCode} onChange={e => setCode(e.target.value)} /></label>
      <button type="submit">Connect</button>
    </form>{error && <p role="alert">{error}</p>}<details><summary>Accessibility settings</summary><AccessibilitySettings /></details></main>
  return (
    <div className="layout">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar currentPage={currentPage} setCurrentPage={setCurrentPage} />

      <div className="main-container">
        <header className="topbar">
          <div className="page-title">{currentPage === 'SkillMaps' ? 'Skill maps & Discord' : currentPage}</div>
          <div className="status-indicator">
            Kingdom:{" "}
            <span className={isConnected ? "badge-online" : "badge-offline"}>
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </header>

        {!isConnected && (
          <div style={{ background: "#2a1213", color: "#f87171", borderBottom: "1px solid var(--accent-red)", padding: "8px 24px", fontSize: "12px" }}>
            Warning: Disconnected from Kingdom Commander. Attempting automatic reconnection...
          </div>
        )}

        <main className="content" id="main-content" tabIndex={-1} aria-label={currentPage === 'SkillMaps' ? 'Skill maps and Discord' : currentPage}>
          {renderPage()}
          <AppearanceSync />
        </main>
      </div>
    </div>
  )
}

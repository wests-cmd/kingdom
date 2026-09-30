import React, { useState, useEffect } from "react"
import { listProfiles, getActiveProfile, setActiveProfile } from "../api"

export default function Profiles() {
  const [profiles, setProfiles] = useState([])
  const [activeProfile, setActiveProfileState] = useState(null)
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [onboardingAnswers, setOnboardingAnswers] = useState({ intent: "research", verbosity: "simple", resources: "free" })
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    try {
      setLoading(true)
      const [profs, active] = await Promise.all([listProfiles(), getActiveProfile()])
      setProfiles(profs || [])
      setActiveProfileState(active)
      if (active && active.profile_details) {
        setSelectedProfile(active.profile_details)
      } else if (profs.length > 0) {
        setSelectedProfile(profs[0])
      }
    } catch (err) {
      console.error("Failed to load profiles:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleActivateProfile = async (profileId) => {
    try {
      const res = await setActiveProfile(profileId)
      setActiveProfileState(res)
      loadData()
    } catch (err) {
      alert("Failed to activate profile: " + err.message)
    }
  }

  const handleOnboardingSubmit = () => {
    const intentProfileMap = {
      research: "prof-researcher",
      buy_sell: "prof-reseller_buyer_seller",
      business: "prof-business",
      learn: "prof-student_learner",
      create: "prof-creator",
      program: "prof-developer",
      news: "prof-news_information",
      community: "prof-community_moderator"
    }
    const targetId = intentProfileMap[onboardingAnswers.intent] || "prof-general_assistant"
    handleActivateProfile(targetId)
    setShowOnboarding(false)
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <h2>Human-Friendly Profiles</h2>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            Choose a profile matching your intent. Kingdom translates your profile into active capabilities and routing rules without exposing complex API configurations.
          </p>
        </div>
        <button className="primary-red" onClick={() => setShowOnboarding(true)}>
          Profile Wizard
        </button>
      </div>

      {activeProfile && activeProfile.profile_details && (
        <div className="card" style={{ marginBottom: "20px", border: "1px solid var(--accent-blue)" }}>
          <div className="card-title" style={{ color: "var(--accent-blue)" }}>Active Active Profile</div>
          <div style={{ fontSize: "18px", fontWeight: "700", marginTop: "4px" }}>
            {activeProfile.profile_details.name}
          </div>
          <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
            {activeProfile.profile_details.description}
          </div>
        </div>
      )}

      {loading ? (
        <p>Loading profiles...</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px", marginBottom: "24px" }}>
          {profiles.map((p) => {
            const isActive = activeProfile && activeProfile.profile_id === p.id
            const isSelected = selectedProfile && selectedProfile.id === p.id

            return (
              <div
                key={p.id}
                className="card"
                style={{
                  cursor: "pointer",
                  border: isActive ? "2px solid var(--accent-green)" : isSelected ? "2px solid var(--accent-red)" : "1px solid var(--surface-border)"
                }}
                onClick={() => setSelectedProfile(p)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: "16px", fontWeight: "600" }}>{p.name}</div>
                  {isActive && <span style={{ fontSize: "10px", background: "var(--accent-green)", color: "#000", padding: "2px 6px", borderRadius: "10px", fontWeight: "700" }}>ACTIVE</span>}
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "8px 0" }}>{p.description}</p>
                <button
                  style={{ width: "100%", marginTop: "8px", fontSize: "12px" }}
                  className={isActive ? "" : "primary-red"}
                  disabled={isActive}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleActivateProfile(p.id)
                  }}
                >
                  {isActive ? "Currently Active" : "Use Profile"}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* Profile Details Panel */}
      {selectedProfile && (
        <div className="card">
          <div className="card-title">Profile Capability Summary: {selectedProfile.name}</div>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "12px" }}>{selectedProfile.description}</p>

          <h4 style={{ fontSize: "14px", marginTop: "12px", marginBottom: "8px" }}>Associated Capabilities</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {selectedProfile.capabilities && selectedProfile.capabilities.length > 0 ? (
              selectedProfile.capabilities.map((c) => (
                <div key={c.id} style={{ background: "#222", padding: "6px 12px", borderRadius: "4px", border: "1px solid var(--surface-border)", fontSize: "12px" }}>
                  <div style={{ fontWeight: "600", color: "#fff" }}>{c.name}</div>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{c.category} • Risk: {c.risk_level}</div>
                </div>
              ))
            ) : (
              <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>No explicit capability restrictions.</p>
            )}
          </div>
        </div>
      )}

      {/* Onboarding Wizard Modal */}
      {showOnboarding && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "500px", maxWidth: "90%" }}>
            <h3>What main task do you want Kingdom to help you with?</h3>
            <div style={{ margin: "16px 0" }}>
              <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>Primary Goal</label>
              <select
                value={onboardingAnswers.intent}
                onChange={(e) => setOnboardingAnswers({ ...onboardingAnswers, intent: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "#111", border: "1px solid var(--surface-border)", color: "#fff" }}
              >
                <option value="research">Deep Research & Synthesis</option>
                <option value="buy_sell">Buy & Sell / E-Commerce</option>
                <option value="business">Business & Market Intelligence</option>
                <option value="learn">Student / Educational Learning</option>
                <option value="create">Creator & Visual Media</option>
                <option value="program">Coding & Software Development</option>
                <option value="news">News & Current Events</option>
                <option value="community">Discord / Community Moderation</option>
              </select>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "20px" }}>
              <button onClick={() => setShowOnboarding(false)}>Cancel</button>
              <button className="primary-red" onClick={handleOnboardingSubmit}>
                Set Active Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

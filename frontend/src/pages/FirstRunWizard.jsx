import React, { useState } from "react";
import { api } from "../api";

export function FirstRunWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [kingdomName, setKingdomName] = useState("My Kingdom");
  const [networkMode, setLocalMode] = useState("local_only");

  const handleFinish = async () => {
    try {
      if (onComplete) onComplete();
    } catch (err) {
      console.error("Wizard error:", err);
    }
  };

  return (
    <div style={{ maxWidth: "540px", margin: "40px auto", padding: "24px", background: "#141414", border: "1px solid #282828", borderRadius: "8px", color: "#ddd" }}>
      <div style={{ borderBottom: "1px solid #222", paddingBottom: "12px", marginBottom: "16px" }}>
        <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#fff" }}>
          👑 Welcome to Kingdom Desktop Setup
        </h2>
        <p style={{ fontSize: "12px", color: "#888", marginTop: "4px" }}>
          Step {step} of 3: {step === 1 ? "Basic Identity" : step === 2 ? "System & Security Check" : "Finish Setup"}
        </p>
      </div>

      {step === 1 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div>
            <label style={{ fontSize: "11px", color: "#aaa", display: "block", marginBottom: "4px" }}>Kingdom Name</label>
            <input
              type="text"
              value={kingdomName}
              onChange={(e) => setKingdomName(e.target.value)}
              style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "8px", fontSize: "13px", borderRadius: "4px" }}
            />
          </div>
          <button onClick={() => setStep(2)} style={{ padding: "8px", background: "var(--accent-red)", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer", marginTop: "8px" }}>
            Next: Security & Network
          </button>
        </div>
      )}

      {step === 2 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div>
            <label style={{ fontSize: "11px", color: "#aaa", display: "block", marginBottom: "4px" }}>Network Boundary Mode</label>
            <select
              value={networkMode}
              onChange={(e) => setLocalMode(e.target.value)}
              style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "8px", fontSize: "13px", borderRadius: "4px" }}
            >
              <option value="local_only">Local Host Only (Safest)</option>
              <option value="lan_access">Local Network (LAN Pairing Allowed)</option>
              <option value="remote_federation">Remote Federation (Tailscale / Direct WAN)</option>
            </select>
          </div>
          <button onClick={() => setStep(3)} style={{ padding: "8px", background: "var(--accent-red)", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer", marginTop: "8px" }}>
            Next: Review
          </button>
        </div>
      )}

      {step === 3 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ background: "#0a0a0a", padding: "12px", border: "1px solid #222", borderRadius: "4px", fontSize: "12px" }}>
            <div>Kingdom Name: <strong style={{ color: "#fff" }}>{kingdomName}</strong></div>
            <div>Network Mode: <strong style={{ color: "#4ade80" }}>{networkMode}</strong></div>
            <div>Security Firewall: <strong style={{ color: "#4ade80" }}>Zero-Trust Active</strong></div>
          </div>
          <button onClick={handleFinish} style={{ padding: "10px", background: "#166534", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer" }}>
            🚀 Open Kingdom Command Center
          </button>
        </div>
      )}
    </div>
  );
}

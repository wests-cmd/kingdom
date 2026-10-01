import React, { useState } from "react";
import api from "../api";
import DevicePairing from "../components/DevicePairing";

export function MobileGateway() {
  const [uploadContent, setUploadContent] = useState("");
  const [filename, setFilename] = useState("pricing_sheet.txt");
  const [domain, setDomain] = useState("Invoices");
  const [isSourceOfTruth, setIsSourceOfTruth] = useState(true);
  const [ingestResult, setIngestResult] = useState(null);

  // Teach Skill State
  const [skillName, setSkillName] = useState("");
  const [skillDesc, setSkillDesc] = useState("");
  const [exampleText, setExampleText] = useState("");
  const [teachResult, setTeachResult] = useState(null);

  const handleUploadKnowledge = async (e) => {
    e.preventDefault();
    try {
      const res = await api.post("/knowledge/upload", {
        content: uploadContent,
        filename: filename,
        domain: domain,
        is_source_of_truth: isSourceOfTruth
      });
      setIngestResult(res.data);
      setUploadContent("");
    } catch (err) {
      alert("Failed to upload knowledge: " + err.message);
    }
  };

  const handleTeachSkill = async (e) => {
    e.preventDefault();
    try {
      const res = await api.post("/skills/teach", {
        name: skillName,
        description: skillDesc,
        examples: [exampleText],
        department: "Workflows"
      });
      setTeachResult(res.data);
      setSkillName("");
      setSkillDesc("");
      setExampleText("");
    } catch (err) {
      alert("Failed to teach skill: " + err.message);
    }
  };

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", color: "var(--text-main)" }}>
      <div style={{ borderBottom: "1px solid var(--surface-border)", paddingBottom: "16px" }}>
        <h1 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)" }}>
          Devices and knowledge
        </h1>
        <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
          Connect a browser companion, save pasted reference text, or create a draft workflow for review.
        </p>
      </div>

      <DevicePairing />
      <div className="knowledge-forms">
        {/* Add Knowledge Text */}
        <div style={{ padding: "16px", background: "var(--surface-dark)", border: "1px solid var(--surface-border)", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)" }}>
            Add knowledge text
          </h2>
          <form onSubmit={handleUploadKnowledge} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Source Document / Text / Transcripts</label>
              <textarea
                rows={4}
                value={uploadContent}
                onChange={(e) => setUploadContent(e.target.value)}
                placeholder="e.g. Standard labor rate is $85/hr. Standard tax rate is 8%."
                style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "8px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Filename</label>
                <input
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Domain Namespace</label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                >
                  <option value="Invoices">Invoices</option>
                  <option value="Pricing">Pricing</option>
                  <option value="Finance">Finance</option>
                  <option value="Personal">Personal</option>
                  <option value="Engineering">Engineering</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <input
                type="checkbox"
                id="sot"
                checked={isSourceOfTruth}
                onChange={(e) => setIsSourceOfTruth(e.target.checked)}
              />
              <label htmlFor="sot" style={{ fontSize: "12px", color: "var(--text-main)" }}>Mark as Source of Truth Document</label>
            </div>

            <button type="submit" style={{ padding: "8px", background: "var(--accent-red)", color: "var(--text-main)", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer" }}>
              Ingest Knowledge
            </button>
          </form>

          {ingestResult && (
            <div style={{ background: "var(--bg-dark)", padding: "10px", border: "1px solid var(--surface-border)", borderRadius: "4px", fontSize: "11px", color: "var(--text-muted)" }}>
              <div>Intent: <span style={{ color: "#4ade80", fontWeight: "700" }}>{ingestResult.extracted?.intent?.primary_intent}</span></div>
              <div>Domain: <span style={{ color: "var(--text-main)" }}>{ingestResult.extracted?.intent?.domain}</span></div>
              {ingestResult.saved_knowledge?.conflicts_detected && (
                <div style={{ color: "#f87171", marginTop: "4px" }}>⚠️ Source-of-Truth Conflict Detected with previous items!</div>
              )}
            </div>
          )}
        </div>

        {/* Teach Kingdom Workflow */}
        <div style={{ padding: "16px", background: "var(--surface-dark)", border: "1px solid var(--surface-border)", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)" }}>
            Create a draft skill
          </h2>
          <form onSubmit={handleTeachSkill} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Skill / Workflow Name</label>
              <input
                type="text"
                placeholder="e.g. Invoice Generation Skill"
                value={skillName}
                onChange={(e) => setSkillName(e.target.value)}
                style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Description & Purpose</label>
              <input
                type="text"
                placeholder="e.g. Formats customer invoices with tax & payment terms"
                value={skillDesc}
                onChange={(e) => setSkillDesc(e.target.value)}
                style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>Demonstration Example Text</label>
              <textarea
                rows={3}
                placeholder="e.g. When creating an invoice, include customer name, line items, standard tax, and net 30 payment terms."
                value={exampleText}
                onChange={(e) => setExampleText(e.target.value)}
                style={{ width: "100%", background: "var(--bg-dark)", border: "1px solid var(--surface-border)", color: "var(--text-main)", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <button type="submit" style={{ padding: "8px", background: "var(--accent-red)", color: "#191c1a", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer" }}>
              Teach Skill
            </button>
          </form>

          {teachResult && (
            <div style={{ background: "var(--bg-dark)", padding: "10px", border: "1px solid var(--surface-border)", borderRadius: "4px", fontSize: "11px", color: "var(--text-muted)" }}>
              <div style={{ color: "#4ade80", fontWeight: "700" }}>{teachResult.message}</div>
              <div>Skill ID: <span style={{ color: "var(--text-main)", fontFamily: "monospace" }}>{teachResult.skill?.id}</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

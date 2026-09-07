import React, { useState, useEffect } from "react";
import { api } from "../api";

export function MobileGateway() {
  const [challenge, setChallenge] = useState(null);
  const [pairedDevices, setPairedDevices] = useState([]);
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

  const fetchChallenge = async () => {
    try {
      const res = await api.post("/mobile/challenge?ttl_seconds=300");
      setChallenge(res.data);
    } catch (err) {
      console.error("Failed to generate mobile challenge:", err);
    }
  };

  useEffect(() => {
    fetchChallenge();
  }, []);

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
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", color: "#ddd" }}>
      <div style={{ borderBottom: "1px solid #222", paddingBottom: "16px" }}>
        <h1 style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>
          📱 Mobile Gateway & Knowledge Teaching Console
        </h1>
        <p style={{ fontSize: "12px", color: "#888", marginTop: "4px" }}>
          Pair mobile devices, ingest universal documents/photos, and teach Kingdom new operational workflows.
        </p>
      </div>

      {/* Challenge Banner */}
      {challenge && (
        <div style={{ padding: "16px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "10px", color: "var(--accent-red)", fontWeight: "700", textTransform: "uppercase" }}>Mobile Pairing Challenge</div>
            <div style={{ fontSize: "24px", fontFamily: "monospace", fontWeight: "700", color: "#fff", tracking: "2px" }}>
              {challenge.code}
            </div>
            <div style={{ fontSize: "11px", color: "#666" }}>Scan or enter on Kingdom Mobile App</div>
          </div>
          <button onClick={fetchChallenge} style={{ padding: "6px 12px", background: "#222", color: "#ccc", border: "1px solid #444", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}>
            🔄 Refresh Challenge
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        {/* Universal Knowledge Ingestion (+ Add) */}
        <div style={{ padding: "16px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: "700", color: "#fff" }}>
            📄 Universal Knowledge Ingestion (+ Add)
          </h2>
          <form onSubmit={handleUploadKnowledge} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Source Document / Text / Transcripts</label>
              <textarea
                rows={4}
                value={uploadContent}
                onChange={(e) => setUploadContent(e.target.value)}
                placeholder="e.g. Standard labor rate is $85/hr. Standard tax rate is 8%."
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "8px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Filename</label>
                <input
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Domain Namespace</label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
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
              <label htmlFor="sot" style={{ fontSize: "12px", color: "#ccc" }}>Mark as Source of Truth Document</label>
            </div>

            <button type="submit" style={{ padding: "8px", background: "var(--accent-red)", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer" }}>
              Ingest Knowledge
            </button>
          </form>

          {ingestResult && (
            <div style={{ background: "#0a0a0a", padding: "10px", border: "1px solid #222", borderRadius: "4px", fontSize: "11px", color: "#aaa" }}>
              <div>Intent: <span style={{ color: "#4ade80", fontWeight: "700" }}>{ingestResult.extracted?.intent?.primary_intent}</span></div>
              <div>Domain: <span style={{ color: "#fff" }}>{ingestResult.extracted?.intent?.domain}</span></div>
              {ingestResult.saved_knowledge?.conflicts_detected && (
                <div style={{ color: "#f87171", marginTop: "4px" }}>⚠️ Source-of-Truth Conflict Detected with previous items!</div>
              )}
            </div>
          )}
        </div>

        {/* Teach Kingdom Workflow */}
        <div style={{ padding: "16px", background: "#141414", border: "1px solid #282828", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: "700", color: "#fff" }}>
            🎓 Teach Kingdom New Skill / Workflow
          </h2>
          <form onSubmit={handleTeachSkill} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Skill / Workflow Name</label>
              <input
                type="text"
                placeholder="e.g. Invoice Generation Skill"
                value={skillName}
                onChange={(e) => setSkillName(e.target.value)}
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Description & Purpose</label>
              <input
                type="text"
                placeholder="e.g. Formats customer invoices with tax & payment terms"
                value={skillDesc}
                onChange={(e) => setSkillDesc(e.target.value)}
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "11px", color: "#aaa", display: "block" }}>Demonstration Example Text</label>
              <textarea
                rows={3}
                placeholder="e.g. When creating an invoice, include customer name, line items, standard tax, and net 30 payment terms."
                value={exampleText}
                onChange={(e) => setExampleText(e.target.value)}
                style={{ width: "100%", background: "#0a0a0a", border: "1px solid #333", color: "#fff", padding: "6px", fontSize: "12px", borderRadius: "4px" }}
                required
              />
            </div>

            <button type="submit" style={{ padding: "8px", background: "#166534", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "600", fontSize: "12px", cursor: "pointer" }}>
              Teach Skill
            </button>
          </form>

          {teachResult && (
            <div style={{ background: "#0a0a0a", padding: "10px", border: "1px solid #222", borderRadius: "4px", fontSize: "11px", color: "#aaa" }}>
              <div style={{ color: "#4ade80", fontWeight: "700" }}>{teachResult.message}</div>
              <div>Skill ID: <span style={{ color: "#fff", fontFamily: "monospace" }}>{teachResult.skill?.id}</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

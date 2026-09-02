import React from "react"

export default function SwarmGraph() {
  const nodes = [
    { id: "planner", x: 250, y: 80, label: "Planner Knight" },
    { id: "coder", x: 100, y: 220, label: "Coder Knight" },
    { id: "researcher", x: 250, y: 220, label: "Researcher Knight" },
    { id: "security", x: 400, y: 220, label: "Security Knight" }
  ]

  const links = [
    { from: { x: 250, y: 80 }, to: { x: 100, y: 220 } },
    { from: { x: 250, y: 80 }, to: { x: 250, y: 220 } },
    { from: { x: 250, y: 80 }, to: { x: 400, y: 220 } }
  ]

  return (
    <div style={{ background: "#181818", padding: "16px", borderRadius: "8px", color: "#fff", marginTop: "16px" }}>
      <h4>Live Swarm Topology Visualizer</h4>
      <svg width="500" height="300" style={{ display: "block", margin: "auto" }}>
        {links.map((l, i) => (
          <line key={i} x1={l.from.x} y1={l.from.y} x2={l.to.x} y2={l.to.y} stroke="#555" strokeWidth="2" />
        ))}
        {nodes.map(n => (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r="25" fill="#4a90e2" stroke="#fff" strokeWidth="2" />
            <text x={n.x} y={n.y + 40} fill="#ddd" fontSize="12" textAnchor="middle">{n.label}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

import React from "react"

export default function RoutingGraph() {
  const nodes = [
    { id: "task", x: 120, y: 150, label: "Task Request" },
    { id: "router", x: 250, y: 150, label: "Hybrid Router" },
    { id: "model", x: 380, y: 150, label: "Assigned Model" }
  ]

  const links = [
    { from: { x: 120, y: 150 }, to: { x: 250, y: 150 } },
    { from: { x: 250, y: 150 }, to: { x: 380, y: 150 } }
  ]

  return (
    <div style={{ background: "#181818", padding: "16px", borderRadius: "8px", color: "#fff", marginTop: "16px" }}>
      <h4>Adaptive Routing Pipeline</h4>
      <svg width="500" height="300" style={{ display: "block", margin: "auto" }}>
        {links.map((l, i) => (
          <line key={i} x1={l.from.x} y1={l.from.y} x2={l.to.x} y2={l.to.y} stroke="#555" strokeWidth="2" />
        ))}
        {nodes.map(n => (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r="25" fill="#bd10e0" stroke="#fff" strokeWidth="2" />
            <text x={n.x} y={n.y + 40} fill="#ddd" fontSize="12" textAnchor="middle">{n.label}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

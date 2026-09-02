import React from "react"

export default function MemoryGraph() {
  const nodes = [
    { id: "context", x: 250, y: 80, label: "Context Engine" },
    { id: "timeline", x: 150, y: 220, label: "Timeline History" },
    { id: "embeddings", x: 350, y: 220, label: "Vector Search" }
  ]

  const links = [
    { from: { x: 250, y: 80 }, to: { x: 150, y: 220 } },
    { from: { x: 250, y: 80 }, to: { x: 350, y: 220 } }
  ]

  return (
    <div style={{ background: "#181818", padding: "16px", borderRadius: "8px", color: "#fff", marginTop: "16px" }}>
      <h4>Memory Knowledge Graph</h4>
      <svg width="500" height="300" style={{ display: "block", margin: "auto" }}>
        {links.map((l, i) => (
          <line key={i} x1={l.from.x} y1={l.from.y} x2={l.to.x} y2={l.to.y} stroke="#555" strokeWidth="2" />
        ))}
        {nodes.map(n => (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r="25" fill="#f5a623" stroke="#fff" strokeWidth="2" />
            <text x={n.x} y={n.y + 40} fill="#ddd" fontSize="12" textAnchor="middle">{n.label}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

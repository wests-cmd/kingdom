import ForceGraph2D from "react-force-graph"

export default function SwarmGraph() {

  const data = {
    nodes: [
      { id: "planner" },
      { id: "coder" },
      { id: "researcher" },
      { id: "security" }
    ],
    links: [
      { source: "planner", target: "coder" },
      { source: "planner", target: "researcher" },
      { source: "planner", target: "security" }
    ]
  }

  return (
    <div style={{ height: "500px" }}>
      <ForceGraph2D graphData={data} />
    </div>
  )
}

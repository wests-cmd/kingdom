import ForceGraph2D from "react-force-graph"

export default function AIMapGraph() {

  const data = {
    nodes: [
      { id: "AI_Map" },
      { id: "Routing" },
      { id: "Memory" },
      { id: "Swarm" }
    ],
    links: [
      { source: "AI_Map", target: "Routing" },
      { source: "AI_Map", target: "Memory" },
      { source: "AI_Map", target: "Swarm" }
    ]
  }

  return (
    <div style={{ height: "500px" }}>
      <ForceGraph2D graphData={data} />
    </div>
  )
}

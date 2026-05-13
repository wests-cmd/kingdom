import ForceGraph2D from "react-force-graph"

export default function RoutingGraph() {

  const data = {
    nodes: [
      { id: "Task" },
      { id: "Router" },
      { id: "Model" }
    ],
    links: [
      { source: "Task", target: "Router" },
      { source: "Router", target: "Model" }
    ]
  }

  return (
    <div style={{ height: "500px" }}>
      <ForceGraph2D graphData={data} />
    </div>
  )
}

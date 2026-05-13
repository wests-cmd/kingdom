import ForceGraph2D from "react-force-graph"

export default function MemoryGraph() {

  const data = {
    nodes: [
      { id: "Context" },
      { id: "Timeline" },
      { id: "Embeddings" }
    ],
    links: [
      { source: "Context", target: "Timeline" },
      { source: "Context", target: "Embeddings" }
    ]
  }

  return (
    <div style={{ height: "500px" }}>
      <ForceGraph2D graphData={data} />
    </div>
  )
}

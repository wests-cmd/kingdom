import React from "react"
import RoutingGraph from "../components/graphs/RoutingGraph"

export default function Routing() {
  return (
    <div>
      <h2>Adaptive Model & Task Routing</h2>

      <div className="card" style={{ margin: "16px 0" }}>
        <div className="card-title">Routing Pipeline Spec</div>
        <div style={{ fontSize: "13px", color: "var(--text-main)" }}>
          Task Request → Complexity Analysis → Model Evaluation → Cost & Latency Scoring → Route Selection
        </div>
      </div>

      <RoutingGraph />
    </div>
  )
}

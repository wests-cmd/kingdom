import React from "react"
import SwarmGraph from "../components/graphs/SwarmGraph"
import RuntimeControls from "../components/runtime/RuntimeControls"
import StatusBar from "../components/common/StatusBar"
import ApprovalsView from "../components/security/ApprovalsView"
import Tasks from "./Tasks"

export default function Dashboard() {

  return (
    <div>

      <h1>Kingdom v40.1</h1>

      <StatusBar />

      <RuntimeControls />

      <ApprovalsView />

      <div style={{ marginTop: "20px" }}>
        <Tasks />
      </div>

      <div style={{ marginTop: "20px" }}>
        <SwarmGraph />
      </div>

    </div>
  )
}

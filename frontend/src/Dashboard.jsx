import SwarmGraph from "../components/graphs/SwarmGraph"
import RuntimeControls from "../components/runtime/RuntimeControls"
import StatusBar from "../components/common/StatusBar"

export default function Dashboard() {

  return (
    <div>

      <h1>Kingdom v40.1</h1>

      <StatusBar />

      <RuntimeControls />

      <SwarmGraph />

    </div>
  )
}

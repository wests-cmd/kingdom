import Dashboard from "./pages/Dashboard"
import Sidebar from "./components/common/Sidebar"

export default function App() {

  return (
    <div className="layout">

      <Sidebar />

      <div className="content">
        <Dashboard />
      </div>

    </div>
  )
}

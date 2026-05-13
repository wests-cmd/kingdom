import { useEffect, useState } from "react"
import api from "../../api"

export default function StatusBar() {

  const [status, setStatus] = useState({})

  useEffect(() => {

    api.get("/status")
      .then(res => setStatus(res.data))

  }, [])

  return (
    <div className="statusbar">

      <div>
        Running: {String(status.running)}
      </div>

      <div>
        Mode: {status.mode}
      </div>

      <div>
        Version: {status.version}
      </div>

    </div>
  )
}

import api from "../../api"

export default function RuntimeControls() {

  const start = async () => {
    await api.post("/start")
  }

  const stop = async () => {
    await api.post("/stop")
  }

  return (
    <div>

      <button onClick={start}>
        Start
      </button>

      <button onClick={stop}>
        Stop
      </button>

    </div>
  )
}

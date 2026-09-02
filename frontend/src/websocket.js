class RealtimeClient {
  constructor() {
    this.socket = null
    this.listeners = []
    this.statusListeners = []
    this.isConnected = false
  }

  connect() {
    try {
      this.socket = new WebSocket("ws://localhost:8000/ws")

      this.socket.onopen = () => {
        this.isConnected = true
        this.notifyStatus(true)
      }

      this.socket.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          this.listeners.forEach(cb => cb(data))
        } catch (e) {}
      }

      this.socket.onclose = () => {
        this.isConnected = false
        this.notifyStatus(false)
        setTimeout(() => this.connect(), 5000)
      }

      this.socket.onerror = () => {
        this.isConnected = false
        this.notifyStatus(false)
      }
    } catch (e) {
      this.isConnected = false
      this.notifyStatus(false)
      setTimeout(() => this.connect(), 5000)
    }
  }

  onEvent(cb) {
    this.listeners.push(cb)
    return () => {
      this.listeners = this.listeners.filter(l => l !== cb)
    }
  }

  onStatusChange(cb) {
    this.statusListeners.push(cb)
    cb(this.isConnected)
    return () => {
      this.statusListeners = this.statusListeners.filter(l => l !== cb)
    }
  }

  notifyStatus(status) {
    this.statusListeners.forEach(cb => cb(status))
  }
}

export const realtime = new RealtimeClient()

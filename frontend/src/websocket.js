class RealtimeClient {
  constructor() {
    this.socket = null
    this.listeners = []
    this.statusListeners = []
    this.isConnected = false
  }

  connect() {
    try {
      const base = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin)
      const url = new URL("/ws", base)
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
      this.socket = new WebSocket(url)

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

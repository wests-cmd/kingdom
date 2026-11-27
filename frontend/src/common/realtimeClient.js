// Transport observation only: connection state never authorizes or verifies work.
export class RealtimeClient {
  constructor(createSocket, clock = globalThis) {
    this.createSocket = createSocket
    this.clock = clock
    this.socket = null
    this.retry = null
    this.enabled = false
    this.listeners = new Set()
    this.statusListeners = new Set()
    this.isConnected = false
  }

  connect() {
    this.enabled = true
    if (this.socket || this.retry !== null) return
    try {
      const socket = this.createSocket()
      this.socket = socket
      const current = () => this.enabled && this.socket === socket
      socket.onopen = () => { if (current()) this.setStatus(true) }
      socket.onmessage = evt => {
        if (!current()) return
        let data
        try { data = JSON.parse(evt.data) } catch { return }
        for (const listener of [...this.listeners]) {
          try { listener(data) } catch { /* One view cannot break another. */ }
        }
      }
      socket.onclose = () => {
        if (!current()) return
        this.socket = null
        this.setStatus(false)
        this.scheduleRetry()
      }
      socket.onerror = () => { if (current()) this.setStatus(false) }
    } catch {
      this.setStatus(false)
      this.scheduleRetry()
    }
  }

  scheduleRetry() {
    if (!this.enabled || this.retry !== null) return
    this.retry = this.clock.setTimeout(() => {
      this.retry = null
      if (this.enabled) this.connect()
    }, 5000)
  }

  disconnect() {
    this.enabled = false
    if (this.retry !== null) this.clock.clearTimeout(this.retry)
    this.retry = null
    const socket = this.socket
    this.socket = null
    if (socket) {
      // Ignore late close/open/message from an obsolete connection.
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null
      try { socket.close() } catch { /* already closed */ }
    }
    this.setStatus(false)
  }

  onEvent(cb) {
    this.listeners.add(cb)
    return () => this.listeners.delete(cb)
  }

  onStatusChange(cb) {
    this.statusListeners.add(cb)
    cb(this.isConnected)
    return () => this.statusListeners.delete(cb)
  }

  setStatus(status) {
    if (this.isConnected === status) return
    this.isConnected = status
    for (const listener of [...this.statusListeners]) {
      try { listener(status) } catch { /* isolate subscribers */ }
    }
  }
}

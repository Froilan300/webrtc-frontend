import { useRobotStore } from '../stores/useRobotStore'

class WebSocketService {
  ws = null
  reconnectTimer = null
  handlers = []

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.ws = new WebSocket('ws://localhost:8080/ws')

    this.ws.onopen = () => {
      useRobotStore.getState().setConnected(true)
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
    }

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        this._dispatch(msg)
      } catch { /* ignorar mensajes malformados */ }
    }

    this.ws.onclose = () => {
      useRobotStore.getState().setConnected(false)
      this.reconnectTimer = setTimeout(() => this.connect(), 3000)
    }

    this.ws.onerror = () => this.ws?.close()
  }

  _dispatch(msg) {
    const store = useRobotStore.getState()

    switch (msg.type) {
      case 'CONNECTION':
        store.setConnected(msg.data.connected)
        break
      case 'TELEMETRY':
        store.updateTelemetry(msg.data.position, msg.data.mode)
        break
      case 'BATTERY':
        store.setBattery(msg.data.level)
        break
      case 'PATROL_STATUS':
        store.setPatrolStatus(msg.data.status, msg.data.progress, msg.data.target ?? -1)
        break
    }

    for (const h of this.handlers) h(msg)
  }

  send(type, payload) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  on(h)  { if (!this.handlers.includes(h)) this.handlers.push(h) }
  off(h) { this.handlers = this.handlers.filter(x => x !== h) }
}

export const ws = new WebSocketService()

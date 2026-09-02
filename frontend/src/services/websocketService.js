/**
 * websocketService — cliente WebSocket (singleton `ws`).
 * Conecta a ws://localhost:8080/ws con reconexión automática. `send(type, payload)`
 * manda comandos al robot; `_dispatch` vuelca los eventos entrantes al store
 * (telemetría, batería, patrulla) y avisa a los suscriptores (`on`/`off`),
 * p. ej. el visor de la nube LiDAR.
 */
import { useRobotStore } from '../stores/useRobotStore'

class WebSocketService {
  ws = null
  reconnectTimer = null
  handlers = []

  /** Abre la conexión WebSocket con el backend. Si se cae, reintenta cada 3 s. */
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

  /** Vuelca un evento entrante del robot al store y avisa a los suscriptores. */
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

  /** Envía un comando `{type, payload}` al robot (si el socket está abierto). */
  send(type, payload) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  on(h)  { if (!this.handlers.includes(h)) this.handlers.push(h) }   // suscribe un handler de eventos (p. ej. LiDAR)
  off(h) { this.handlers = this.handlers.filter(x => x !== h) }      // da de baja un handler
}

export const ws = new WebSocketService()

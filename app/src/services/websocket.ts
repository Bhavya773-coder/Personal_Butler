/**
 * JARVIS Core — WebSocket Service
 * 
 * Manages WebSocket connection to the FastAPI backend.
 * Auto-reconnects with exponential backoff.
 * Routes incoming events to registered callbacks.
 */

export type JarvisEventType =
  | 'transcription_partial'
  | 'transcription_final'
  | 'llm_token'
  | 'tts_sentence_started'
  | 'tts_sentence_done'
  | 'tool_started'
  | 'tool_progress'
  | 'tool_done'
  | 'permission_required'
  | 'interrupted'
  | 'error'
  | 'final'
  | 'thinking'

export interface JarvisEvent {
  type: JarvisEventType
  [key: string]: any
}

type EventCallback = (event: JarvisEvent) => void

const WS_URL = 'ws://localhost:8000/ws/events'
const MAX_RECONNECT_DELAY = 10000
const INITIAL_RECONNECT_DELAY = 1000

class WebSocketService {
  private ws: WebSocket | null = null
  private listeners: Map<string, Set<EventCallback>> = new Map()
  private globalListeners: Set<EventCallback> = new Set()
  private reconnectDelay = INITIAL_RECONNECT_DELAY
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private _isConnected = false
  private shouldReconnect = true

  get isConnected(): boolean {
    return this._isConnected
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      this.ws = new WebSocket(WS_URL)

      this.ws.onopen = () => {
        console.log('[WS] Connected to JARVIS backend')
        this._isConnected = true
        this.reconnectDelay = INITIAL_RECONNECT_DELAY
        this.emit({ type: 'connected' } as any)
      }

      this.ws.onmessage = (event) => {
        try {
          const data: JarvisEvent = JSON.parse(event.data)
          this.emit(data)
        } catch (e) {
          console.error('[WS] Failed to parse message:', e)
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this._isConnected = false
        this.emit({ type: 'disconnected' } as any)
        if (this.shouldReconnect) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error)
        this._isConnected = false
      }
    } catch (e) {
      console.error('[WS] Connection failed:', e)
      if (this.shouldReconnect) {
        this.scheduleReconnect()
      }
    }
  }

  disconnect(): void {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }
    this.ws?.close()
    this.ws = null
    this._isConnected = false
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    console.log(`[WS] Reconnecting in ${this.reconnectDelay}ms...`)
    this.reconnectTimer = setTimeout(() => {
      this.connect()
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY)
    }, this.reconnectDelay)
  }

  /** Send a message to the backend */
  send(message: { type: string; [key: string]: any }): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('[WS] Not connected. Message not sent:', message)
    }
  }

  /** Send a chat message */
  sendChat(message: string): void {
    this.send({ type: 'chat', message })
  }

  /** Send a task message */
  sendTask(message: string): void {
    this.send({ type: 'task', message })
  }

  /** Send interrupt signal */
  sendInterrupt(): void {
    this.send({ type: 'interrupt' })
  }

  /** Send permission response */
  sendPermissionResponse(requestId: string, approved: boolean): void {
    this.send({ type: 'permission_response', request_id: requestId, approved })
  }

  /** Listen for a specific event type */
  on(eventType: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }
    this.listeners.get(eventType)!.add(callback)
    return () => {
      this.listeners.get(eventType)?.delete(callback)
    }
  }

  /** Listen for all events */
  onAny(callback: EventCallback): () => void {
    this.globalListeners.add(callback)
    return () => {
      this.globalListeners.delete(callback)
    }
  }

  private emit(event: JarvisEvent): void {
    // Notify type-specific listeners
    this.listeners.get(event.type)?.forEach((cb) => cb(event))
    // Notify global listeners
    this.globalListeners.forEach((cb) => cb(event))
  }
}

// Singleton instance
export const wsService = new WebSocketService()

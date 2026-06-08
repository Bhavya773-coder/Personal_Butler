/**
 * JARVIS Core — Audio / Speech Recognition Service
 * 
 * Delegates speech-to-text to the local Python backend via WebSockets
 * to bypass Electron's built-in webkitSpeechRecognition API key restrictions.
 */

import { wsService } from './websocket'

export type TranscriptionCallback = (text: string, isFinal: boolean) => void
export type StatusCallback = (status: 'listening' | 'stopped' | 'error', error?: string) => void

class AudioService {
  private _isListening = false
  private onTranscription: TranscriptionCallback | null = null
  private onStatus: StatusCallback | null = null
  private unsubscribers: (() => void)[] = []

  get isListening(): boolean {
    return this._isListening
  }

  get isSupported(): boolean {
    // Backend STT is always supported locally
    return true
  }

  /** Initialize speech recognition */
  init(onTranscription: TranscriptionCallback, onStatus: StatusCallback): void {
    this.onTranscription = onTranscription
    this.onStatus = onStatus

    // Clean up any old listeners
    this.unsubscribers.forEach(unsub => unsub())
    this.unsubscribers = []

    // Listen to WebSocket events from backend
    const unsubPartial = wsService.on('transcription_partial', (event: any) => {
      if (this._isListening) {
        this.onTranscription?.(event.text || '', false)
      }
    })

    const unsubFinal = wsService.on('transcription_final', (event: any) => {
      if (this._isListening) {
        this.onTranscription?.(event.text || '', true)
        // Automatically set listening state to stopped or keep listening based on mode
        this.stop()
      }
    })

    const unsubError = wsService.on('stt_error', (event: any) => {
      this.onStatus?.('error', event.message || 'Speech recognition failed')
      this.stop()
    })

    this.unsubscribers.push(unsubPartial, unsubFinal, unsubError)
  }

  /** Start listening */
  start(): void {
    this._isListening = true
    wsService.send({ type: 'start_stt' })
    this.onStatus?.('listening')
  }

  /** Stop listening */
  stop(): void {
    if (!this._isListening) return
    this._isListening = false
    wsService.send({ type: 'stop_stt' })
    this.onStatus?.('stopped')
  }

  /** Toggle listening */
  toggle(): void {
    if (this._isListening) {
      this.stop()
    } else {
      this.start()
    }
  }
}

// Singleton
export const audioService = new AudioService()

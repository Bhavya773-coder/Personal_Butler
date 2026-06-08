/**
 * JARVIS Core — Main Application
 *
 * Root component managing all state: WebSocket events, transcript,
 * Jarvis state machine, permissions, and audio.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import JarvisHUD, { JarvisState } from './components/JarvisHUD'
import TranscriptPanel, { TranscriptEntry } from './components/TranscriptPanel'
import CommandInput from './components/CommandInput'
import StatusBar from './components/StatusBar'
import PermissionModal, { PermissionRequest } from './components/PermissionModal'
import { wsService, JarvisEvent } from './services/websocket'
import { checkHealth, sendInterrupt } from './services/api'
import { audioService } from './services/audio'

let entryCounter = 0
function nextId(): string {
  return `entry-${++entryCounter}-${Date.now()}`
}

const App: React.FC = () => {
  const [state, setState] = useState<JarvisState>('idle')
  const [isConnected, setIsConnected] = useState(false)
  const [ollamaStatus, setOllamaStatus] = useState<any>(null)
  const [entries, setEntries] = useState<TranscriptEntry[]>([])
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [isListening, setIsListening] = useState(false)
  const [permissionRequest, setPermissionRequest] = useState<PermissionRequest | null>(null)
  const [interimText, setInterimText] = useState('')

  // Track the current streaming assistant entry
  const streamingIdRef = useRef<string | null>(null)

  // ── Health Check ──
  const doHealthCheck = useCallback(async () => {
    try {
      const health = await checkHealth()
      setOllamaStatus(health.ollama)
      setIsConnected(true)
    } catch {
      setIsConnected(false)
      setOllamaStatus(null)
    }
  }, [])

  // ── WebSocket Events ──
  useEffect(() => {
    wsService.connect()

    const unsub = wsService.onAny((event: JarvisEvent) => {
      switch (event.type) {
        case 'connected' as any:
          setIsConnected(true)
          doHealthCheck()
          break

        case 'disconnected' as any:
          setIsConnected(false)
          break

        case 'thinking':
          setState('thinking')
          break

        case 'llm_token': {
          setState('speaking')
          const token = event.token || ''
          if (!streamingIdRef.current) {
            // Start a new assistant entry
            const id = nextId()
            streamingIdRef.current = id
            setEntries((prev) => [
              ...prev,
              { id, role: 'assistant', content: token, timestamp: new Date(), isStreaming: true },
            ])
          } else {
            // Append to existing streaming entry
            const sid = streamingIdRef.current
            setEntries((prev) =>
              prev.map((e) =>
                e.id === sid ? { ...e, content: e.content + token } : e
              )
            )
          }
          break
        }

        case 'tool_started':
          setState('thinking')
          setActiveTool(event.message || event.tool || 'Working...')
          setEntries((prev) => [
            ...prev,
            {
              id: nextId(),
              role: 'tool',
              content: `⚙️ ${event.message || `Running ${event.tool}...`}`,
              timestamp: new Date(),
            },
          ])
          break

        case 'tool_done':
          setActiveTool(null)
          break

        case 'permission_required':
          setPermissionRequest({
            id: event.request_id || `perm-${Date.now()}`,
            action: event.action || 'unknown',
            description: event.description || 'Action requires permission',
            level: event.level === 'dangerous' ? 'dangerous' : 'confirm',
            details: event.details,
          })
          break

        case 'tts_sentence_started':
          setState('speaking')
          break

        case 'tts_sentence_done':
          // Stay in speaking state until final
          break

        case 'final':
          // Finalize streaming entry
          if (streamingIdRef.current) {
            const sid = streamingIdRef.current
            setEntries((prev) =>
              prev.map((e) =>
                e.id === sid ? { ...e, isStreaming: false } : e
              )
            )
            streamingIdRef.current = null
          } else if (event.response) {
            // No streaming happened, add the full response
            setEntries((prev) => [
              ...prev,
              { id: nextId(), role: 'assistant', content: event.response, timestamp: new Date() },
            ])
          }
          setState('idle')
          setActiveTool(null)
          break

        case 'interrupted':
          setState('interrupted')
          setActiveTool(null)
          if (streamingIdRef.current) {
            const sid = streamingIdRef.current
            setEntries((prev) =>
              prev.map((e) =>
                e.id === sid ? { ...e, isStreaming: false, content: e.content + ' [stopped]' } : e
              )
            )
            streamingIdRef.current = null
          }
          setEntries((prev) => [
            ...prev,
            { id: nextId(), role: 'assistant', content: 'Stopped.', timestamp: new Date() },
          ])
          setTimeout(() => setState('idle'), 2000)
          break

        case 'error':
          setState('error')
          setActiveTool(null)
          setEntries((prev) => [
            ...prev,
            { id: nextId(), role: 'system', content: `❌ ${event.message || 'An error occurred'}`, timestamp: new Date() },
          ])
          setTimeout(() => setState('idle'), 3000)
          break
      }
    })

    // Health check interval
    doHealthCheck()
    const healthTimer = setInterval(doHealthCheck, 30000)

    return () => {
      unsub()
      clearInterval(healthTimer)
      wsService.disconnect()
    }
  }, [doHealthCheck])

  // ── Electron Interrupt Shortcut ──
  useEffect(() => {
    if (window.jarvis) {
      const cleanup = window.jarvis.onInterrupt(() => {
        handleInterrupt()
      })
      return cleanup
    }
    // Fallback: keyboard listener for Ctrl+Space when not in Electron
    const handleKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.code === 'Space') {
        e.preventDefault()
        handleInterrupt()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  // ── Audio (STT) Setup ──
  useEffect(() => {
    if (audioService.isSupported) {
      audioService.init(
        // Transcription callback
        (text, isFinal) => {
          if (isFinal) {
            setInterimText('')
            // Add user entry and send to backend
            handleSend(text)
          } else {
            setInterimText(text)
          }
        },
        // Status callback
        (status, error) => {
          if (status === 'listening') {
            setIsListening(true)
            setState('listening')
          } else {
            setIsListening(false)
            if (state === 'listening') setState('idle')
          }
          if (error) {
            setEntries((prev) => [
              ...prev,
              { id: nextId(), role: 'system', content: `🎤 ${error}`, timestamp: new Date() },
            ])
          }
        }
      )
    }
  }, [])

  // ── Handlers ──

  const handleSend = useCallback((message: string) => {
    // Add user entry to transcript
    setEntries((prev) => [
      ...prev,
      { id: nextId(), role: 'user', content: message, timestamp: new Date() },
    ])

    // Send via WebSocket
    setState('thinking')
    streamingIdRef.current = null
    wsService.sendChat(message)
  }, [])

  const handleInterrupt = useCallback(async () => {
    try {
      wsService.sendInterrupt()
      await sendInterrupt()
    } catch {
      // WS interrupt already sent
    }
    audioService.stop()
    setIsListening(false)
  }, [])

  const handleMicToggle = useCallback(() => {
    audioService.toggle()
  }, [])

  const handlePermissionApprove = useCallback((id: string) => {
    wsService.sendPermissionResponse(id, true)
    setPermissionRequest(null)
  }, [])

  const handlePermissionDeny = useCallback((id: string) => {
    wsService.sendPermissionResponse(id, false)
    setPermissionRequest(null)
  }, [])

  const isProcessing = state === 'thinking' || state === 'speaking'

  return (
    <div className="app" id="jarvis-app">
      <div className="app__main">
        {/* Left: HUD */}
        <div className="app__hud-section">
          <JarvisHUD state={state} />
          {interimText && (
            <div className="app__interim-text">
              <span className="app__interim-label">Hearing:</span>
              <span className="app__interim-content">{interimText}</span>
            </div>
          )}
        </div>

        {/* Right: Transcript */}
        <div className="app__transcript-section">
          <TranscriptPanel entries={entries} />
        </div>
      </div>

      {/* Bottom: Input */}
      <CommandInput
        onSend={handleSend}
        onMicToggle={handleMicToggle}
        onInterrupt={handleInterrupt}
        isListening={isListening}
        isProcessing={isProcessing}
        isMicSupported={audioService.isSupported}
      />

      {/* Bottom Bar: Status */}
      <StatusBar
        state={state}
        isConnected={isConnected}
        ollamaStatus={ollamaStatus}
        activeTool={activeTool}
      />

      {/* Permission Modal Overlay */}
      <PermissionModal
        request={permissionRequest}
        onApprove={handlePermissionApprove}
        onDeny={handlePermissionDeny}
      />
    </div>
  )
}

export default App

/**
 * JARVIS Core — Status Bar
 * 
 * Shows connection status, Ollama status, current state, and active tool.
 */

import React from 'react'
import { JarvisState } from './JarvisHUD'

interface StatusBarProps {
  state: JarvisState
  isConnected: boolean
  ollamaStatus: { running: boolean; model_available: boolean; error: string | null } | null
  activeTool: string | null
}

const StatusBar: React.FC<StatusBarProps> = ({
  state,
  isConnected,
  ollamaStatus,
  activeTool,
}) => {
  return (
    <div className="status-bar" id="status-bar">
      {/* Connection Status */}
      <div className={`status-bar__item ${isConnected ? 'status-bar__item--ok' : 'status-bar__item--error'}`}>
        <span className="status-bar__dot" />
        <span>{isConnected ? 'Backend Connected' : 'Disconnected'}</span>
      </div>

      {/* Ollama Status */}
      {ollamaStatus && (
        <div className={`status-bar__item ${ollamaStatus.running && ollamaStatus.model_available ? 'status-bar__item--ok' : 'status-bar__item--warn'}`}>
          <span className="status-bar__dot" />
          <span>
            {!ollamaStatus.running
              ? 'Ollama Offline'
              : !ollamaStatus.model_available
                ? 'Model Missing'
                : 'Ollama Ready'}
          </span>
        </div>
      )}

      {/* Active Tool */}
      {activeTool && (
        <div className="status-bar__item status-bar__item--active">
          <span className="status-bar__dot status-bar__dot--pulse" />
          <span>{activeTool}</span>
        </div>
      )}

      {/* Current State */}
      <div className="status-bar__item status-bar__state">
        <span className="status-bar__state-label">{state.toUpperCase()}</span>
      </div>

      {/* Version */}
      <div className="status-bar__item status-bar__version">
        JARVIS Core v0.2.1
      </div>
    </div>
  )
}

export default StatusBar

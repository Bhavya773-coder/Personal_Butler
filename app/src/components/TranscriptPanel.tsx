/**
 * JARVIS Core — Transcript Panel
 * 
 * Scrollable conversation log showing user messages,
 * Jarvis responses (streamed), and tool execution status.
 */

import React, { useEffect, useRef } from 'react'

export interface TranscriptEntry {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

interface TranscriptPanelProps {
  entries: TranscriptEntry[]
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ entries }) => {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries])

  const getRoleIcon = (role: string): string => {
    switch (role) {
      case 'user': return '👤'
      case 'assistant': return '🤖'
      case 'tool': return '⚙️'
      case 'system': return '📡'
      default: return '💬'
    }
  }

  const getRoleLabel = (role: string): string => {
    switch (role) {
      case 'user': return 'You'
      case 'assistant': return 'Jarvis'
      case 'tool': return 'Tool'
      case 'system': return 'System'
      default: return role
    }
  }

  return (
    <div className="transcript-panel" id="transcript-panel">
      <div className="transcript-panel__header">
        <span className="transcript-panel__title">Conversation</span>
        <span className="transcript-panel__count">{entries.length} messages</span>
      </div>
      <div className="transcript-panel__messages">
        {entries.length === 0 ? (
          <div className="transcript-panel__empty">
            <p>Say something or type a command to get started.</p>
            <p className="transcript-panel__hint">
              Try: "What is my CPU usage?" or "Open Notepad"
            </p>
          </div>
        ) : (
          entries.map((entry) => (
            <div
              key={entry.id}
              className={`message message--${entry.role} ${entry.isStreaming ? 'message--streaming' : ''}`}
            >
              <div className="message__header">
                <span className="message__icon">{getRoleIcon(entry.role)}</span>
                <span className="message__role">{getRoleLabel(entry.role)}</span>
                <span className="message__time">
                  {entry.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <div className="message__content">
                {entry.content}
                {entry.isStreaming && <span className="message__cursor">▊</span>}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

export default TranscriptPanel

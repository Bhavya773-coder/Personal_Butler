/**
 * JARVIS Core — Command Input
 * 
 * Text input with send button, mic toggle, and interrupt button.
 */

import React, { useState, useRef } from 'react'

interface CommandInputProps {
  onSend: (message: string) => void
  onMicToggle: () => void
  onInterrupt: () => void
  isListening: boolean
  isProcessing: boolean
  isMicSupported: boolean
}

const CommandInput: React.FC<CommandInputProps> = ({
  onSend,
  onMicToggle,
  onInterrupt,
  isListening,
  isProcessing,
  isMicSupported,
}) => {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (trimmed) {
      onSend(trimmed)
      setInput('')
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e)
    }
  }

  return (
    <div className="command-input" id="command-input">
      <form className="command-input__form" onSubmit={handleSubmit}>
        {/* Mic Button */}
        {isMicSupported && (
          <button
            type="button"
            className={`command-input__btn command-input__mic ${isListening ? 'command-input__mic--active' : ''}`}
            onClick={onMicToggle}
            title={isListening ? 'Stop listening' : 'Start listening'}
            id="mic-button"
          >
            {isListening ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            )}
          </button>
        )}

        {/* Text Input */}
        <input
          ref={inputRef}
          type="text"
          className="command-input__field"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? 'Listening... speak now' : 'Type a command or ask a question...'}
          disabled={isProcessing}
          id="command-field"
          autoComplete="off"
        />

        {/* Send Button */}
        <button
          type="submit"
          className="command-input__btn command-input__send"
          disabled={!input.trim() || isProcessing}
          title="Send"
          id="send-button"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>

        {/* Interrupt Button */}
        <button
          type="button"
          className="command-input__btn command-input__interrupt"
          onClick={onInterrupt}
          title="Interrupt (Ctrl+Space)"
          id="interrupt-button"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="6" y="4" width="4" height="16"/>
            <rect x="14" y="4" width="4" height="16"/>
          </svg>
        </button>
      </form>

      <div className="command-input__hint">
        Press <kbd>Enter</kbd> to send • <kbd>Ctrl+Space</kbd> to interrupt
      </div>
    </div>
  )
}

export default CommandInput

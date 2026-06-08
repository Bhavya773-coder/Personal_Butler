/**
 * JARVIS Core — Main HUD Component
 * 
 * Central animated orb with state-dependent visual feedback.
 */

import React from 'react'

export type JarvisState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'interrupted' | 'error'

interface JarvisHUDProps {
  state: JarvisState
}

const STATE_CONFIG: Record<JarvisState, { label: string; color: string; glow: string }> = {
  idle: { label: 'Ready', color: '#00d4ff', glow: 'rgba(0, 212, 255, 0.3)' },
  listening: { label: 'Listening...', color: '#00ff88', glow: 'rgba(0, 255, 136, 0.4)' },
  thinking: { label: 'Thinking...', color: '#ffaa00', glow: 'rgba(255, 170, 0, 0.4)' },
  speaking: { label: 'Speaking', color: '#4488ff', glow: 'rgba(68, 136, 255, 0.4)' },
  interrupted: { label: 'Stopped', color: '#ff4444', glow: 'rgba(255, 68, 68, 0.3)' },
  error: { label: 'Error', color: '#ff2222', glow: 'rgba(255, 34, 34, 0.4)' },
}

const JarvisHUD: React.FC<JarvisHUDProps> = ({ state }) => {
  const config = STATE_CONFIG[state]

  return (
    <div className="jarvis-hud" id="jarvis-hud">
      <div
        className={`orb orb--${state}`}
        style={{
          '--orb-color': config.color,
          '--orb-glow': config.glow,
        } as React.CSSProperties}
      >
        <div className="orb__core" />
        <div className="orb__ring orb__ring--1" />
        <div className="orb__ring orb__ring--2" />
        <div className="orb__ring orb__ring--3" />
      </div>
      <p className="jarvis-hud__label" style={{ color: config.color }}>
        {config.label}
      </p>
    </div>
  )
}

export default JarvisHUD

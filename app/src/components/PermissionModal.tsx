/**
 * JARVIS Core — Permission Modal
 * 
 * Overlay modal shown when an action requires user confirmation.
 * Auto-denies on timeout (30s).
 */

import React, { useEffect, useState } from 'react'

export interface PermissionRequest {
  id: string
  action: string
  description: string
  level: 'confirm' | 'dangerous'
  details?: Record<string, any>
}

interface PermissionModalProps {
  request: PermissionRequest | null
  onApprove: (id: string) => void
  onDeny: (id: string) => void
}

const TIMEOUT_SECONDS = 30

const PermissionModal: React.FC<PermissionModalProps> = ({ request, onApprove, onDeny }) => {
  const [countdown, setCountdown] = useState(TIMEOUT_SECONDS)

  useEffect(() => {
    if (!request) return

    setCountdown(TIMEOUT_SECONDS)
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          onDeny(request.id)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [request])

  if (!request) return null

  const isDangerous = request.level === 'dangerous'

  return (
    <div className="permission-modal__overlay" id="permission-modal">
      <div className={`permission-modal ${isDangerous ? 'permission-modal--dangerous' : ''}`}>
        <div className="permission-modal__header">
          <span className="permission-modal__icon">
            {isDangerous ? '⚠️' : '🔐'}
          </span>
          <h3 className="permission-modal__title">
            {isDangerous ? 'Dangerous Action' : 'Permission Required'}
          </h3>
        </div>

        <div className="permission-modal__body">
          <p className="permission-modal__description">{request.description}</p>
          <div className="permission-modal__details">
            <span className="permission-modal__action">Action: {request.action}</span>
            <span className="permission-modal__level">Level: {request.level.toUpperCase()}</span>
          </div>
          {request.details && Object.keys(request.details).length > 0 && (
            <pre className="permission-modal__json">
              {JSON.stringify(request.details, null, 2)}
            </pre>
          )}
        </div>

        <div className="permission-modal__footer">
          <button
            className="permission-modal__btn permission-modal__btn--deny"
            onClick={() => onDeny(request.id)}
            id="permission-deny-button"
          >
            Deny
          </button>
          <button
            className="permission-modal__btn permission-modal__btn--approve"
            onClick={() => onApprove(request.id)}
            id="permission-approve-button"
          >
            Approve
          </button>
          <span className="permission-modal__countdown">
            Auto-deny in {countdown}s
          </span>
        </div>
      </div>
    </div>
  )
}

export default PermissionModal

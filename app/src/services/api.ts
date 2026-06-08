/**
 * JARVIS Core — REST API Service
 * 
 * HTTP client for the FastAPI backend REST endpoints.
 */

const API_BASE = 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  try {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return await response.json()
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Cannot connect to JARVIS backend. Is it running?')
    }
    throw error
  }
}

/** Health check */
export async function checkHealth(): Promise<{
  status: string
  ollama: { running: boolean; model_available: boolean; error: string | null }
  ws_clients: number
}> {
  return request('/health')
}

/** Get system info */
export async function getSystemInfo(): Promise<any> {
  return request('/sysinfo')
}

/** Send chat message (non-streaming, prefer WebSocket) */
export async function sendChat(message: string): Promise<{ response: string }> {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

/** Send task request */
export async function sendTask(message: string): Promise<{ response: string }> {
  return request('/task', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

/** Send interrupt */
export async function sendInterrupt(): Promise<{ status: string }> {
  return request('/interrupt', { method: 'POST' })
}

/** Approve permission */
export async function approvePermission(requestId: string): Promise<{ success: boolean }> {
  return request('/permission/approve', {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId, approved: true }),
  })
}

/** Deny permission */
export async function denyPermission(requestId: string): Promise<{ success: boolean }> {
  return request('/permission/deny', {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId, approved: false }),
  })
}

/** Get logs */
export async function getLogs(limit = 50): Promise<{ logs: any[] }> {
  return request(`/logs?limit=${limit}`)
}

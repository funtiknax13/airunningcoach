export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const BASE = ''   // proxy в vite.config.ts перенаправляет на :8000

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

export function setToken(token: string | null): void {
  token ? localStorage.setItem('access_token', token)
        : localStorage.removeItem('access_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

async function request<T>(
  path: string,
  method = 'GET',
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 204) return undefined as T

  const data = await res.json()
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'object' && detail !== null && !Array.isArray(detail)
      ? (detail.message ?? JSON.stringify(detail))
      : Array.isArray(detail)
        ? detail.map((e: { msg: string }) => e.msg).join('; ')
        : (detail ?? 'Server error')
    if (res.status === 401 && !path.includes('/api/auth/')) {
      setToken(null)
      window.location.href = '/'
    }
    throw new ApiError(message, res.status, detail)
  }
  return data as T
}

async function requestRaw<T>(
  path: string,
  method = 'POST',
  body?: FormData,
): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { method, headers, body })

  if (res.status === 204) return undefined as T

  const data = await res.json()
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((e: { msg: string }) => e.msg).join('; ')
      : (detail?.message ?? JSON.stringify(detail) ?? 'Server error')
    if (res.status === 401 && !path.includes('/api/auth/')) {
      setToken(null); window.location.href = '/'
    }
    throw new ApiError(message, res.status, detail)
  }
  return data as T
}

export const api = { request, requestRaw, getToken, setToken, isAuthenticated }

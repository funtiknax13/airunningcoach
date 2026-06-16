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

// AI-эндпоинты могут отвечать долго (генерация плана/чат) — даём щедрый таймаут,
// но не бесконечный, чтобы мёртвое соединение не висело вечно.
const TIMEOUT_MS = 120_000

async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    return await fetch(url, { ...init, signal: ctrl.signal })
  } catch (e) {
    // Сетевой сбой / таймаут / abort → статус 0 (НЕ 401 — сессию не сбрасываем)
    const msg = (e as Error)?.name === 'AbortError'
      ? 'Превышено время ожидания ответа сервера'
      : 'Нет соединения с сервером'
    throw new ApiError(msg, 0)
  } finally {
    clearTimeout(timer)
  }
}

async function request<T>(
  path: string,
  method = 'GET',
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetchWithTimeout(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 204) return undefined as T

  // 5xx от nginx (504/502) приходит как HTML — res.json() упадёт. Отдаём чистую ошибку.
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'object' && detail !== null && !Array.isArray(detail)
      ? (detail.message ?? JSON.stringify(detail))
      : Array.isArray(detail)
        ? detail.map((e: { msg: string }) => e.msg).join('; ')
        : (detail ?? `Ошибка сервера (${res.status})`)
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

  const res = await fetchWithTimeout(`${BASE}${path}`, { method, headers, body })

  if (res.status === 204) return undefined as T

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((e: { msg: string }) => e.msg).join('; ')
      : (detail?.message ?? JSON.stringify(detail) ?? `Ошибка сервера (${res.status})`)
    if (res.status === 401 && !path.includes('/api/auth/')) {
      setToken(null); window.location.href = '/'
    }
    throw new ApiError(message, res.status, detail)
  }
  return data as T
}

export const api = { request, requestRaw, getToken, setToken, isAuthenticated }

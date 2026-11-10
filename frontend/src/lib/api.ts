import { config } from '@/lib/config'
import { supabase } from '@/lib/supabase'

/**
 * Error shape returned by the backend for every failed request:
 *   { "error": { "code": "not_found", "message": "...", "details": ... } }
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  /** JSON-serialisable body. Use `rawBody` for FormData (audio uploads later). */
  json?: unknown
  rawBody?: BodyInit
  timeoutMs?: number
}

async function authHeader(): Promise<Record<string, string>> {
  // getSession() returns the cached session and refreshes the token if it is about to expire.
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Thin fetch wrapper used by every feature. It attaches the Supabase access token,
 * so no component ever has to deal with auth headers itself.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, rawBody, timeoutMs = 15_000, headers, ...init } = options
  const auth = await authHeader()

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  let response: Response
  try {
    response = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      signal: init.signal ?? controller.signal,
      headers: {
        Accept: 'application/json',
        ...auth,
        ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rawBody,
    })
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === 'AbortError'
    throw new ApiError(
      0,
      aborted ? 'timeout' : 'network_error',
      aborted
        ? 'The server took too long to respond. It may be waking up — try again in a moment.'
        : 'Could not reach the server. Check your connection or that the backend is running.',
    )
  } finally {
    clearTimeout(timer)
  }

  if (response.status === 204) return undefined as T

  const body: unknown = await response.json().catch(() => null)

  if (response.status === 401 && auth.Authorization) {
    // Our session was rejected (expired/revoked). Signing out sends the user to /login.
    await supabase.auth.signOut({ scope: 'local' })
  }

  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)
      ?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? `Request failed with status ${response.status}`,
      error?.details,
    )
  }

  return body as T
}

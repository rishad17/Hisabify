import { config } from '@/lib/config'

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

/**
 * Thin fetch wrapper used by every feature.
 * Phase 1 will add the Supabase access token as an Authorization header here,
 * so no component ever has to deal with auth headers itself.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, rawBody, timeoutMs = 15_000, headers, ...init } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  let response: Response
  try {
    response = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      signal: init.signal ?? controller.signal,
      headers: {
        Accept: 'application/json',
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

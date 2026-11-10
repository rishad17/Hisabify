/**
 * Central place for reading build-time environment variables.
 *
 * Only variables prefixed with VITE_ are exposed to the browser by Vite.
 * NEVER put secrets (Gemini/Groq keys, DB passwords, service-role keys) here —
 * anything in a VITE_ variable ends up in the public JavaScript bundle.
 *
 * The Supabase URL and publishable (anon) key ARE public by design: they only let the
 * browser talk to Supabase Auth. Our data tables are locked with RLS, and all financial
 * data goes through the FastAPI backend.
 */

function read(name: string, fallback?: string): string {
  const value = (import.meta.env[name] as string | undefined) ?? fallback
  if (value === undefined || value === '') {
    throw new Error(`Missing environment variable ${name}. Copy .env.example to .env.local.`)
  }
  return value
}

export const config = {
  /** Base URL of the FastAPI backend, without a trailing slash. */
  apiUrl: read('VITE_API_URL', 'http://localhost:8000').replace(/\/+$/, ''),
  supabaseUrl: read('VITE_SUPABASE_URL'),
  supabaseKey: read('VITE_SUPABASE_PUBLISHABLE_KEY'),
} as const

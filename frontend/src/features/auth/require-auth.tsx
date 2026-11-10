import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from '@/features/auth/auth-provider'

/** Route guard: renders child routes only for signed-in users. */
export function RequireAuth() {
  const { session, loading } = useAuth()
  const location = useLocation()

  if (loading) return <FullPageSpinner />
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

/** Inverse guard for /login and /signup: signed-in users go straight to the app. */
export function RedirectIfAuthed() {
  const { session, loading } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (loading) return <FullPageSpinner />
  if (session) return <Navigate to={from} replace />
  return <Outlet />
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-svh items-center justify-center bg-background" role="status">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden />
      <span className="sr-only">Loading…</span>
    </div>
  )
}

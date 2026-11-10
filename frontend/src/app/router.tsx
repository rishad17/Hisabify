import { lazy, Suspense, type ComponentType, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router'

import { AppShell } from '@/app/app-shell'
import { RouteError } from '@/app/route-error'
import { LoginPage } from '@/features/auth/login-page'
import { FullPageSpinner, RedirectIfAuthed, RequireAuth } from '@/features/auth/require-auth'
import { SignupPage } from '@/features/auth/signup-page'

/**
 * Pages are loaded on demand (code splitting): the first visit downloads only the shell
 * and the page you open; charts (Recharts) load only where they're shown.
 */
function page(load: () => Promise<ComponentType>): ReactNode {
  const Component = lazy(async () => ({ default: await load() }))
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Component />
    </Suspense>
  )
}

export const router = createBrowserRouter([
  {
    errorElement: <RouteError />,
    children: [
      {
        element: <RedirectIfAuthed />,
        children: [
          { path: '/login', element: <LoginPage /> },
          { path: '/signup', element: <SignupPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell />,
            errorElement: <RouteError />,
            children: [
              { path: '/', element: page(() => import('@/features/ledger/dashboard-page').then((m) => m.DashboardPage)) },
              { path: '/transactions', element: page(() => import('@/features/ledger/transactions-page').then((m) => m.TransactionsPage)) },
              { path: '/plan', element: page(() => import('@/features/planning/plan-page').then((m) => m.PlanPage)) },
              { path: '/insights', element: page(() => import('@/features/insights/insights-page').then((m) => m.InsightsPage)) },
              { path: '/wallets', element: page(() => import('@/features/ledger/wallets-page').then((m) => m.WalletsPage)) },
              { path: '/settings', element: page(() => import('@/features/settings/settings-page').then((m) => m.SettingsPage)) },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

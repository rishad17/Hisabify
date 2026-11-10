import { createBrowserRouter, Navigate } from 'react-router'

import { AppShell } from '@/app/app-shell'
import { LoginPage } from '@/features/auth/login-page'
import { RedirectIfAuthed, RequireAuth } from '@/features/auth/require-auth'
import { SignupPage } from '@/features/auth/signup-page'
import { DashboardPage } from '@/features/ledger/dashboard-page'
import { TransactionsPage } from '@/features/ledger/transactions-page'
import { WalletsPage } from '@/features/ledger/wallets-page'
import { SettingsPage } from '@/features/settings/settings-page'

export const router = createBrowserRouter([
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
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/transactions', element: <TransactionsPage /> },
          { path: '/wallets', element: <WalletsPage /> },
          { path: '/settings', element: <SettingsPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

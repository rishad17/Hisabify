import { createBrowserRouter, Navigate } from 'react-router'

import { AppShell } from '@/app/app-shell'
import { LoginPage } from '@/features/auth/login-page'
import { RedirectIfAuthed, RequireAuth } from '@/features/auth/require-auth'
import { SignupPage } from '@/features/auth/signup-page'
import { HomePage } from '@/features/home/home-page'

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
        children: [{ path: '/', element: <HomePage /> }],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

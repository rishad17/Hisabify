import { LogOut, Wallet } from 'lucide-react'
import { Link, Outlet } from 'react-router'

import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-provider'

/** Layout for signed-in pages. Navigation links are added as features land. */
export function AppShell() {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-2 px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <Wallet className="size-5 text-primary" aria-hidden />
            TakaWise AI
          </Link>
          <div className="flex items-center gap-2">
            <span className="hidden max-w-48 truncate text-sm text-muted-foreground sm:inline">
              {user?.email}
            </span>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut}>
              <LogOut aria-hidden />
              <span className="sr-only sm:not-sr-only">Sign out</span>
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

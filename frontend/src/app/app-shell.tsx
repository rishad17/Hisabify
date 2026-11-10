import {
  AlertCircle,
  LayoutDashboard,
  ListOrdered,
  Loader2,
  LogOut,
  Settings,
  Target,
  Wallet,
  WalletCards,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'

import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-provider'
import { useMe } from '@/features/me/api'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { cn } from '@/lib/utils'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: ListOrdered },
  { to: '/plan', label: 'Plan', icon: Target },
  { to: '/wallets', label: 'Wallets', icon: WalletCards },
  { to: '/settings', label: 'Settings', icon: Settings },
]

/** Layout for signed-in pages: top bar + nav (bottom tab bar on phones). */
export function AppShell() {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-2 px-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2 font-semibold">
              <Wallet className="size-5 text-primary" aria-hidden />
              TakaWise AI
            </Link>
            <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground',
                      isActive && 'bg-muted font-medium text-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden max-w-48 truncate text-sm text-muted-foreground lg:inline">{user?.email}</span>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut}>
              <LogOut aria-hidden />
              <span className="sr-only sm:not-sr-only">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Extra bottom padding on phones so content isn't hidden behind the tab bar. */}
      <main className="mx-auto max-w-6xl px-4 pt-6 pb-28 md:pb-10">
        <AccountGate />
      </main>

      {/* Phone: floating add button + bottom tab bar */}
      <AddTransactionButton floating className="fixed right-4 bottom-20 z-30 md:hidden" />
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-0.5 py-2 text-[11px] text-muted-foreground',
                isActive && 'font-medium text-primary',
              )
            }
          >
            <item.icon className="size-5" aria-hidden />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

/**
 * GET /me creates the account (profile, categories, Cash wallet) on first login.
 * Pages render only after it succeeds, so no page ever sees a half-created account.
 */
function AccountGate() {
  const me = useMe()
  if (me.isPending) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center" role="status">
        <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Loading your account… the free server can take up to a minute to wake up.
        </p>
      </div>
    )
  }
  if (me.isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center" role="alert">
        <AlertCircle className="size-6 text-destructive" aria-hidden />
        <p className="font-medium">Couldn't load your account</p>
        <p className="max-w-sm text-sm text-muted-foreground">{me.error.message}</p>
        <Button variant="outline" onClick={() => me.refetch()}>
          Try again
        </Button>
      </div>
    )
  }
  return <Outlet />
}

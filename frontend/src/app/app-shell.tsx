import { AlertCircle, Loader2, LogOut, Settings } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'

import { Logo } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-provider'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { useMe } from '@/features/me/api'
import { APP_TIMEZONE } from '@/lib/dates'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/plan', label: 'Plan' },
  { to: '/insights', label: 'Insights' },
  { to: '/wallets', label: 'Wallets' },
  { to: '/settings', label: 'Settings' },
]

const MOBILE_LEFT = NAV.slice(0, 2)
const MOBILE_RIGHT = [NAV[2], NAV[3]]

const today = () =>
  new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: APP_TIMEZONE }).format(
    new Date(),
  )

/** Editorial masthead (desktop) + flat bottom bar (phones). */
export function AppShell() {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-20 bg-background/95 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          {/* Masthead row */}
          <div className="flex h-16 items-center justify-between gap-4">
            <Link to="/" aria-label="Hisabify home">
              <Logo />
            </Link>
            <p className="hidden text-sm text-muted-foreground md:block">{today()}</p>
            <div className="flex items-center gap-1 sm:gap-2">
              <AddTransactionButton className="hidden md:inline-flex" />
              <ThemeToggle />
              <Button asChild variant="ghost" size="icon" className="md:hidden" aria-label="Settings">
                <Link to="/settings">
                  <Settings aria-hidden />
                </Link>
              </Button>
              <Button variant="ghost" size="icon" onClick={signOut} aria-label={`Sign out ${user?.email ?? ''}`} title="Sign out">
                <LogOut aria-hidden />
              </Button>
            </div>
          </div>
          {/* Section nav: text links on a thick rule */}
          <nav aria-label="Main" className="hidden gap-6 border-b-2 border-foreground md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    '-mb-0.5 border-b-[3px] border-transparent pt-1 pb-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground',
                    isActive && 'border-primary text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="border-b-2 border-foreground md:hidden" />
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-8 pb-28 sm:px-6 md:pb-16 lg:px-8 lg:pt-10">
        <AccountGate />
      </main>

      {/* Phone: flat bottom bar with a square add button in the middle */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 items-center border-t-2 border-foreground bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        {MOBILE_LEFT.map((item) => (
          <TabLink key={item.to} {...item} />
        ))}
        <div className="flex justify-center py-1.5">
          <AddTransactionButton floating className="size-11 rounded-md shadow-none" />
        </div>
        {MOBILE_RIGHT.map((item) => (
          <TabLink key={item.to} {...item} />
        ))}
      </nav>
    </div>
  )
}

function TabLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        cn(
          'flex h-full items-center justify-center border-t-[3px] border-transparent text-[12px] font-semibold text-muted-foreground',
          isActive && 'border-primary text-foreground',
        )
      }
    >
      {label}
    </NavLink>
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
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Loading your account. The free server can take up to a minute to wake up.
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


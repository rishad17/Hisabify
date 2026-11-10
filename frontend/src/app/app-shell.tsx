import {
  AlertCircle,
  ChartColumn,
  LayoutDashboard,
  ListOrdered,
  Loader2,
  LogOut,
  Settings,
  Target,
  WalletCards,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'

import { Logo } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-provider'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { useMe } from '@/features/me/api'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon }

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: ListOrdered },
  { to: '/plan', label: 'Plan', icon: Target },
  { to: '/insights', label: 'Insights', icon: ChartColumn },
  { to: '/wallets', label: 'Wallets', icon: WalletCards },
  { to: '/settings', label: 'Settings', icon: Settings },
]

// Phone tab bar: 4 tabs + a raised "add" button in the middle.
const MOBILE_LEFT = NAV.slice(0, 2)
const MOBILE_RIGHT = [NAV[2], NAV[3]]

/** Signed-in layout: sidebar on desktop, top bar + bottom tabs on phones. */
export function AppShell() {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* ---------- Desktop sidebar ---------- */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-sidebar lg:flex">
        <Link to="/" className="flex h-16 items-center px-5" aria-label="Hisabify home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="flex-1 space-y-1 px-3 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground',
                  isActive && 'bg-accent text-accent-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-primary" aria-hidden />}
                  <item.icon className={cn('size-[18px]', isActive && 'text-primary')} aria-hidden />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
          <div className="px-1 pt-4">
            <AddTransactionButton className="w-full" />
          </div>
        </nav>
        <div className="space-y-3 border-t p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-secondary-foreground uppercase">
              {user?.email?.[0] ?? '?'}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground" title={user?.email ?? undefined}>
              {user?.email}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut} className="ml-auto">
              <LogOut aria-hidden /> Sign out
            </Button>
          </div>
        </div>
      </aside>

      {/* ---------- Phone / tablet top bar ---------- */}
      <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur lg:hidden">
        <div className="flex h-14 items-center justify-between gap-2 px-4">
          <Link to="/" aria-label="Hisabify home">
            <Logo />
          </Link>
          <div className="flex items-center gap-1">
            <Button asChild variant="ghost" size="icon" aria-label="Wallets">
              <Link to="/wallets">
                <WalletCards aria-hidden />
              </Link>
            </Button>
            <Button asChild variant="ghost" size="icon" aria-label="Settings">
              <Link to="/settings">
                <Settings aria-hidden />
              </Link>
            </Button>
            <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out">
              <LogOut aria-hidden />
            </Button>
          </div>
        </div>
      </header>

      {/* ---------- Content ---------- */}
      <main className="lg:pl-64">
        {/* Extra bottom padding on phones so content isn't hidden behind the tab bar. */}
        <div className="mx-auto max-w-6xl px-4 pt-6 pb-28 sm:px-6 lg:px-8 lg:pt-8 lg:pb-12">
          <AccountGate />
        </div>
      </main>

      {/* ---------- Phone bottom tab bar ---------- */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 items-end border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {MOBILE_LEFT.map((item) => (
          <TabLink key={item.to} item={item} />
        ))}
        <div className="flex justify-center">
          <AddTransactionButton floating className="-mt-5 size-14 shadow-lg ring-4 ring-background" />
        </div>
        {MOBILE_RIGHT.map((item) => (
          <TabLink key={item.to} item={item} />
        ))}
      </nav>
    </div>
  )
}

function TabLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex flex-col items-center gap-0.5 pt-2 pb-2 text-[11px] text-muted-foreground transition-colors',
          isActive && 'font-semibold text-primary',
        )
      }
    >
      <item.icon className="size-5" aria-hidden />
      {item.label}
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

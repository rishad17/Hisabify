import {
  AlertCircle,
  ChartColumn,
  LayoutDashboard,
  ListOrdered,
  Loader2,
  Settings,
  Target,
  WalletCards,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { AccountMenu } from '@/components/account-menu'
import { Logo } from '@/components/brand'
import { Button } from '@/components/ui/button'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { useMe } from '@/features/me/api'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon }

const NAV_GROUPS: { label?: string; items: NavItem[] }[] = [
  {
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/transactions', label: 'Transactions', icon: ListOrdered },
    ],
  },
  {
    label: 'Planning',
    items: [
      { to: '/plan', label: 'Plan', icon: Target },
      { to: '/insights', label: 'Insights', icon: ChartColumn },
    ],
  },
  {
    label: 'Account',
    items: [
      { to: '/wallets', label: 'Wallets', icon: WalletCards },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]
const NAV = NAV_GROUPS.flatMap((g) => g.items)

// Phone tab bar: 4 tabs + a raised "add" button in the middle.
const MOBILE_LEFT = NAV.slice(0, 2)
const MOBILE_RIGHT = [NAV[2], NAV[3]]

/** Signed-in layout: sidebar on desktop, top bar + bottom tabs on phones. */
export function AppShell() {
  const { pathname } = useLocation()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      {/* ---------- Desktop sidebar ---------- */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r bg-sidebar lg:flex">
        <Link to="/" className="flex h-16 shrink-0 items-center px-5" aria-label="Hisabify home">
          <Logo />
        </Link>
        <div className="px-3 pb-2">
          <AddTransactionButton className="w-full" />
        </div>
        <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-3">
          {NAV_GROUPS.map((group, i) => (
            <div key={group.label ?? i} className="space-y-0.5">
              {group.label && (
                <p className="px-3 pb-1.5 text-[11px] font-medium tracking-wider text-muted-foreground/80 uppercase">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => (
                <SideLink key={item.to} item={item} />
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t p-2">
          <AccountMenu />
        </div>
      </aside>

      {/* ---------- Phone / tablet top bar ---------- */}
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/80 backdrop-blur-md supports-backdrop-filter:bg-background/70 lg:hidden">
        <div className="flex h-14 items-center justify-between gap-2 px-4">
          <Link to="/" aria-label="Hisabify home">
            <Logo />
          </Link>
          <AccountMenu variant="icon" />
        </div>
      </header>

      {/* ---------- Content ---------- */}
      <main id="main" className="lg:pl-60">
        {/* Extra bottom padding on phones so content isn't hidden behind the tab bar. */}
        <div className="mx-auto max-w-6xl px-4 pt-6 pb-32 sm:px-6 lg:px-10 lg:pt-10 lg:pb-16">
          {/* Re-keyed per page so each page fades in gently. */}
          <div key={pathname} className="animate-in duration-300 ease-out fade-in-0 slide-in-from-bottom-1">
            <AccountGate />
          </div>
        </div>
      </main>

      {/* ---------- Phone bottom tab bar ---------- */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 items-end border-t border-border/70 bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
      >
        {MOBILE_LEFT.map((item) => (
          <TabLink key={item.to} item={item} />
        ))}
        <div className="flex justify-center">
          <AddTransactionButton floating className="-mt-6 size-14 shadow-raised ring-4 ring-background" />
        </div>
        {MOBILE_RIGHT.map((item) => (
          <TabLink key={item.to} item={item} />
        ))}
      </nav>
    </div>
  )
}

function SideLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'group flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground',
          isActive && 'bg-accent text-accent-foreground hover:bg-accent hover:text-accent-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <item.icon
            className={cn(
              'size-[18px] transition-colors',
              isActive ? 'text-primary' : 'text-muted-foreground/80 group-hover:text-foreground',
            )}
            aria-hidden
          />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

function TabLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'group flex flex-col items-center gap-1 pt-2 pb-2 text-[11px] font-medium text-muted-foreground transition-colors',
          isActive && 'text-primary',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={cn(
              'flex h-7 w-12 items-center justify-center rounded-full transition-colors duration-200',
              isActive && 'bg-accent',
            )}
          >
            <item.icon className="size-5" aria-hidden />
          </span>
          {item.label}
        </>
      )}
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

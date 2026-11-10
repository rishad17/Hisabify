import { AlertCircle, ArrowDownLeft, ArrowUpRight, ChevronRight, Scale } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link } from 'react-router'

import { PageHeader } from '@/components/brand'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { QuickEntry } from '@/features/assistant/quick-entry'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { Money } from '@/features/ledger/amount'
import { useOverview, useRecentTransactions, useWallets, type Overview, type Wallet } from '@/features/ledger/api'
import { TransactionList } from '@/features/ledger/transaction-list'
import { WalletIcon } from '@/features/ledger/wallet-icon'
import { useMe } from '@/features/me/api'
import { BudgetAlerts } from '@/features/planning/budget-alerts'
import { SafeToSpendCard } from '@/features/planning/safe-to-spend-card'
import { APP_TIMEZONE, currentMonth, formatMonth } from '@/lib/dates'
import { formatTaka, isNegative } from '@/lib/money'

// Charts pull in Recharts (the biggest library) — load them after the rest of the page.
const CategoryBreakdownChart = lazy(async () => ({
  default: (await import('@/features/insights/charts')).CategoryBreakdownChart,
}))
const DailySpendingChart = lazy(async () => ({
  default: (await import('@/features/insights/charts')).DailySpendingChart,
}))

function greeting(): string {
  const hour = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hour12: false, timeZone: APP_TIMEZONE }).format(new Date()))
  if (hour < 5) return 'Good night'
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function DashboardPage() {
  const month = currentMonth()
  const me = useMe() // also guarantees the account exists before other calls
  const overview = useOverview(month)
  const wallets = useWallets()
  const recent = useRecentTransactions(6)

  if (me.isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertTitle>Couldn't load your account</AlertTitle>
        <AlertDescription>
          <p>{me.error.message}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => me.refetch()}>
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  const name = me.data?.profile.display_name ?? me.data?.email?.split('@')[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title={name ? `${greeting()}, ${name}` : greeting()}
        description={`Here's your money in ${formatMonth(month)}.`}
      />

      <BudgetAlerts />

      <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <BalanceHero overview={overview.data} wallets={wallets.data} loading={overview.isPending} />
        <SafeToSpendCard />
      </div>
      {overview.isError && <p className="text-sm text-destructive">{overview.error.message}</p>}

      <QuickEntry />

      <section aria-labelledby="charts-heading" className="space-y-3">
        <SectionTitle id="charts-heading" title="This month" to="/insights" link="All insights" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Suspense fallback={<Skeleton className="h-72 w-full rounded-xl" />}>
            <CategoryBreakdownChart month={month} />
            <DailySpendingChart month={month} />
          </Suspense>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="recent-heading" className="space-y-3">
          <SectionTitle id="recent-heading" title="Recent transactions" to="/transactions" link="See all" />
          {recent.isPending && <Skeleton className="h-48 w-full rounded-xl" />}
          {recent.isError && <p className="text-sm text-destructive">{recent.error.message}</p>}
          {recent.isSuccess && recent.data.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <span className="flex size-12 items-center justify-center rounded-2xl bg-secondary text-2xl" aria-hidden>
                  ৳
                </span>
                <p className="font-medium">No transactions yet</p>
                <p className="max-w-xs text-sm text-muted-foreground">
                  Record your first expense — try typing “ajke 50 taka cha” above.
                </p>
                <AddTransactionButton />
              </CardContent>
            </Card>
          )}
          {recent.isSuccess && recent.data.length > 0 && <TransactionList items={recent.data} groupByDay={false} />}
        </section>

        <section aria-labelledby="wallets-heading" className="space-y-3">
          <SectionTitle id="wallets-heading" title="Wallets" to="/wallets" link="Manage" />
          {wallets.isPending && <Skeleton className="h-32 w-full rounded-xl" />}
          {wallets.isSuccess && (
            <ul className="divide-y overflow-hidden rounded-xl border bg-card shadow-xs">
              {wallets.data.map((w) => (
                <li key={w.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                    <WalletIcon type={w.type} className="size-4" />
                  </span>
                  <span className="flex-1 truncate text-sm font-medium">{w.name}</span>
                  <Money value={w.balance} className="text-sm font-semibold" />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

function SectionTitle({ id, title, to, link }: { id: string; title: string; to: string; link: string }) {
  return (
    <div className="flex items-center justify-between">
      <h2 id={id} className="text-base font-semibold tracking-tight">
        {title}
      </h2>
      <Button asChild variant="ghost" size="sm" className="text-primary hover:text-primary">
        <Link to={to}>
          {link} <ChevronRight aria-hidden />
        </Link>
      </Button>
    </div>
  )
}

/** The headline card: total balance on a deep-emerald gradient, with this month's flow. */
function BalanceHero({
  overview,
  wallets,
  loading,
}: {
  overview: Overview | undefined
  wallets: Wallet[] | undefined
  loading: boolean
}) {
  return (
    <section
      aria-label="Total balance and this month"
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-hero-from to-hero-to p-6 text-white shadow-lg shadow-primary/10"
    >
      {/* Decorative: soft light + a large faint ৳ watermark */}
      <span className="pointer-events-none absolute -top-24 -right-16 size-64 rounded-full bg-white/10 blur-2xl" aria-hidden />
      <span className="pointer-events-none absolute -top-6 right-4 text-[160px] leading-none font-bold text-white/[0.045] select-none" aria-hidden>
        ৳
      </span>

      <div className="relative space-y-5">
        <div>
          <p className="text-sm font-medium text-hero-muted">Total balance</p>
          {loading || !overview ? (
            <Skeleton className="mt-2 h-10 w-48 bg-white/20" />
          ) : (
            <p className="mt-1 text-4xl font-semibold tracking-tight sm:text-[44px]">
              {formatTaka(overview.total_balance, { trimZeroDecimals: true })}
            </p>
          )}
        </div>

        {wallets && wallets.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Wallet balances">
            {wallets.slice(0, 4).map((w) => (
              <li key={w.id} className="flex items-center gap-1.5 rounded-full bg-white/12 px-3 py-1 text-xs ring-1 ring-white/15">
                <WalletIcon type={w.type} className="size-3.5 text-gold" />
                <span className="text-hero-muted">{w.name}</span>
                <span className="font-semibold">{formatTaka(w.balance, { trimZeroDecimals: true })}</span>
              </li>
            ))}
          </ul>
        )}

        <dl className="grid grid-cols-3 gap-3 border-t border-white/15 pt-4">
          <HeroStat icon={<ArrowDownLeft className="size-4" aria-hidden />} label="Income" value={overview?.income} />
          <HeroStat icon={<ArrowUpRight className="size-4" aria-hidden />} label="Expenses" value={overview?.expense} />
          <HeroStat icon={<Scale className="size-4" aria-hidden />} label="Net" value={overview?.net} signed />
        </dl>
      </div>
    </section>
  )
}

function HeroStat({ icon, label, value, signed }: { icon: ReactNode; label: string; value?: string; signed?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-xs text-hero-muted">
        <span className="flex size-5 items-center justify-center rounded-md bg-white/15">{icon}</span>
        {label}
      </dt>
      <dd className="mt-1 truncate text-base font-semibold sm:text-lg">
        {value === undefined ? '—' : formatTaka(value, { trimZeroDecimals: true, showPlus: signed && !isNegative(value) })}
      </dd>
    </div>
  )
}

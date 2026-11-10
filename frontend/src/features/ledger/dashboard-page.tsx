import { AlertCircle, ArrowRight } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { Link } from 'react-router'

import { Kicker, PageHeader } from '@/components/brand'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { QuickEntry } from '@/features/assistant/quick-entry'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { BigMoney, Money } from '@/features/ledger/amount'
import { useOverview, useRecentTransactions, useWallets, type Overview, type Wallet } from '@/features/ledger/api'
import { TransactionList } from '@/features/ledger/transaction-list'
import { useMe } from '@/features/me/api'
import { BudgetAlerts } from '@/features/planning/budget-alerts'
import { SafeToSpendCard } from '@/features/planning/safe-to-spend-card'
import { APP_TIMEZONE, currentMonth, formatMonth } from '@/lib/dates'
import { formatTaka, isNegative } from '@/lib/money'
import { cn } from '@/lib/utils'

// Charts pull in Recharts (the biggest library), so they load after the rest of the page.
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
    <div className="space-y-12">
      <PageHeader kicker={`Overview · ${formatMonth(month)}`} title={name ? `${greeting()}, ${name}.` : `${greeting()}.`} />

      <BudgetAlerts />

      {/* The headline figures, set like a front page */}
      <section aria-label="Balance and this month" className="grid gap-x-10 gap-y-12 lg:grid-cols-[1.45fr_1fr]">
        <BalanceStory overview={overview.data} wallets={wallets.data} loading={overview.isPending} />
        <SafeToSpendCard />
      </section>
      {overview.isError && <p className="text-sm text-destructive">{overview.error.message}</p>}

      <QuickEntry />

      <section aria-labelledby="charts-heading" className="space-y-5">
        <SectionTitle id="charts-heading" title="This month" to="/insights" link="All insights" />
        <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
          <Suspense fallback={<Skeleton className="h-72 w-full" />}>
            <CategoryBreakdownChart month={month} />
            <DailySpendingChart month={month} />
          </Suspense>
        </div>
      </section>

      <div className="grid gap-x-10 gap-y-12 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="recent-heading" className="space-y-4">
          <SectionTitle id="recent-heading" title="Latest entries" to="/transactions" link="All transactions" />
          {recent.isPending && <Skeleton className="h-48 w-full" />}
          {recent.isError && <p className="text-sm text-destructive">{recent.error.message}</p>}
          {recent.isSuccess && recent.data.length === 0 && (
            <div className="space-y-3 border-t-2 border-foreground py-8">
              <p className="font-display text-2xl font-bold">Nothing recorded yet.</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                Type “ajke 50 taka cha” in the box above, or add your first entry by hand.
              </p>
              <AddTransactionButton />
            </div>
          )}
          {recent.isSuccess && recent.data.length > 0 && <TransactionList items={recent.data} groupByDay={false} />}
        </section>

        <section aria-labelledby="wallets-heading" className="space-y-4">
          <SectionTitle id="wallets-heading" title="Wallets" to="/wallets" link="Manage" />
          {wallets.isPending && <Skeleton className="h-32 w-full" />}
          {wallets.isSuccess && (
            <ul className="border-t-2 border-foreground">
              {wallets.data.map((w) => (
                <li key={w.id} className="flex items-baseline justify-between gap-3 border-b py-3">
                  <span className="text-[15px] font-medium">{w.name}</span>
                  <Money value={w.balance} className="font-display text-lg font-semibold" />
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
    <div className="flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-2xl font-bold sm:text-[28px]">
        {title}
      </h2>
      <Link to={to} className="group inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
        {link} <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
      </Link>
    </div>
  )
}

/** Total balance as a giant figure, then this month's flow as three ruled figures. */
function BalanceStory({
  overview,
  wallets,
  loading,
}: {
  overview: Overview | undefined
  wallets: Wallet[] | undefined
  loading: boolean
}) {
  return (
    <div className="space-y-7 border-t-2 border-foreground pt-4">
      <div className="space-y-2">
        <Kicker>Total balance, all wallets</Kicker>
        {loading || !overview ? (
          <Skeleton className="h-20 w-72" />
        ) : (
          <BigMoney value={overview.total_balance} className="text-[64px] sm:text-[88px]" />
        )}
        {wallets && wallets.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {wallets.map((w, i) => (
              <span key={w.id}>
                {i > 0 && <span className="px-2 text-border">/</span>}
                {w.name} <span className="font-semibold text-foreground">{formatTaka(w.balance, { trimZeroDecimals: true })}</span>
              </span>
            ))}
          </p>
        )}
      </div>

      <dl className="grid grid-cols-3 border-t">
        <Figure label="In this month" value={overview?.income} tone="in" />
        <Figure label="Out this month" value={overview?.expense} />
        <Figure label="Net" value={overview?.net} signed />
      </dl>
    </div>
  )
}

function Figure({ label, value, signed, tone }: { label: string; value?: string; signed?: boolean; tone?: 'in' }) {
  const negative = value !== undefined && isNegative(value)
  return (
    <div className="border-r py-3 pr-3 last:border-r-0 [&:not(:first-child)]:pl-4">
      <dt className="text-[11px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">{label}</dt>
      <dd
        className={cn(
          'mt-1 truncate font-display text-xl font-bold sm:text-2xl',
          tone === 'in' && 'text-primary',
          negative && 'text-destructive',
        )}
      >
        {value === undefined ? '-' : formatTaka(value, { trimZeroDecimals: true, showPlus: signed && !negative })}
      </dd>
    </div>
  )
}

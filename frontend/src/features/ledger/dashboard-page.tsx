import { AlertCircle, ArrowDownLeft, ArrowUpRight, ChevronRight, Scale, WalletMinimal } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link } from 'react-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { QuickEntry } from '@/features/assistant/quick-entry'
import { BudgetAlerts } from '@/features/planning/budget-alerts'
import { SafeToSpendCard } from '@/features/planning/safe-to-spend-card'
import { useOverview, useRecentTransactions, useWallets } from '@/features/ledger/api'
import { Money } from '@/features/ledger/amount'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { TransactionList } from '@/features/ledger/transaction-list'
import { WalletIcon } from '@/features/ledger/wallet-icon'
import { useMe } from '@/features/me/api'
import { currentMonth, formatMonth } from '@/lib/dates'

// Charts pull in Recharts (~ the biggest library) — load them after the rest of the page.
const CategoryBreakdownChart = lazy(async () => ({
  default: (await import('@/features/insights/charts')).CategoryBreakdownChart,
}))
const DailySpendingChart = lazy(async () => ({
  default: (await import('@/features/insights/charts')).DailySpendingChart,
}))

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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{name ? `Hi, ${name}` : 'Dashboard'}</h1>
          <p className="text-sm text-muted-foreground">{formatMonth(month)} overview</p>
        </div>
        <AddTransactionButton className="hidden sm:inline-flex" />
      </div>

      <QuickEntry />

      <BudgetAlerts />

      <SafeToSpendCard />

      {/* Overview cards */}
      <section aria-label="This month" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Total balance"
          icon={<WalletMinimal className="size-4" aria-hidden />}
          value={overview.data?.total_balance}
          loading={overview.isPending}
          hint="All wallets, right now"
        />
        <StatCard
          label="Income"
          icon={<ArrowDownLeft className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden />}
          value={overview.data?.income}
          loading={overview.isPending}
          hint="This month"
        />
        <StatCard
          label="Expenses"
          icon={<ArrowUpRight className="size-4" aria-hidden />}
          value={overview.data?.expense}
          loading={overview.isPending}
          hint="This month"
        />
        <StatCard
          label="Net"
          icon={<Scale className="size-4" aria-hidden />}
          value={overview.data?.net}
          loading={overview.isPending}
          hint="Income − expenses"
        />
      </section>
      {overview.isError && <p className="text-sm text-destructive">{overview.error.message}</p>}

      <section aria-labelledby="charts-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="charts-heading" className="font-semibold">
            This month
          </h2>
          <Button asChild variant="ghost" size="sm">
            <Link to="/insights">
              All insights <ChevronRight aria-hidden />
            </Link>
          </Button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Suspense fallback={<Skeleton className="h-72 w-full" />}>
            <CategoryBreakdownChart month={month} />
            <DailySpendingChart month={month} />
          </Suspense>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        {/* Recent transactions */}
        <section aria-labelledby="recent-heading" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 id="recent-heading" className="font-semibold">
              Recent transactions
            </h2>
            <Button asChild variant="ghost" size="sm">
              <Link to="/transactions">
                See all <ChevronRight aria-hidden />
              </Link>
            </Button>
          </div>
          {recent.isPending && <Skeleton className="h-48 w-full" />}
          {recent.isError && <p className="text-sm text-destructive">{recent.error.message}</p>}
          {recent.isSuccess && recent.data.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="font-medium">No transactions yet</p>
                <p className="max-w-xs text-sm text-muted-foreground">
                  Record your first expense — for example, ৳50 for tea from Cash.
                </p>
                <AddTransactionButton />
              </CardContent>
            </Card>
          )}
          {recent.isSuccess && recent.data.length > 0 && (
            <TransactionList items={recent.data} groupByDay={false} />
          )}
        </section>

        {/* Wallets */}
        <section aria-labelledby="wallets-heading" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 id="wallets-heading" className="font-semibold">
              Wallets
            </h2>
            <Button asChild variant="ghost" size="sm">
              <Link to="/wallets">
                Manage <ChevronRight aria-hidden />
              </Link>
            </Button>
          </div>
          {wallets.isPending && <Skeleton className="h-32 w-full" />}
          {wallets.isSuccess && (
            <ul className="divide-y rounded-lg border bg-card">
              {wallets.data.map((w) => (
                <li key={w.id} className="flex items-center gap-3 px-3 py-2.5">
                  <WalletIcon type={w.type} className="size-4 text-muted-foreground" />
                  <span className="flex-1 truncate text-sm">{w.name}</span>
                  <Money value={w.balance} className="text-sm font-medium" />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

function StatCard({
  label,
  icon,
  value,
  loading,
  hint,
}: {
  label: string
  icon: ReactNode
  value: string | undefined
  loading: boolean
  hint: string
}) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardDescription className="flex items-center justify-between gap-2">
          {label}
          {icon}
        </CardDescription>
        <CardTitle className="text-lg sm:text-2xl">
          {loading || value === undefined ? <Skeleton className="h-7 w-24" /> : <Money value={value} />}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 text-xs text-muted-foreground">{hint}</CardContent>
    </Card>
  )
}

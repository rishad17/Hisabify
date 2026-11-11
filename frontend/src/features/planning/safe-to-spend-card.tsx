import { ChevronDown, Info, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Money } from '@/features/ledger/amount'
import { useSafeToSpend } from '@/features/planning/api'
import { formatTaka, isNegative } from '@/lib/money'

/**
 * "How much can I still spend?" — after reserving unpaid bills, savings and essentials.
 * Every number comes from the backend; this card only displays and explains them.
 */
export function SafeToSpendCard() {
  const q = useSafeToSpend()
  const [open, setOpen] = useState(false)

  if (q.isPending) return <Skeleton className="h-40 w-full" />
  if (q.isError) return <p className="text-sm text-destructive">{q.error.message}</p>
  const s = q.data

  const limitedByBudget =
    s.flexible_budget_left !== null && s.recommended === s.flexible_budget_left && s.recommended !== s.available

  return (
    <Card className="h-full">
      <CardHeader className="pb-0">
        <CardDescription className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 font-medium text-foreground">
            <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-primary">
              <ShieldCheck className="size-4" aria-hidden />
            </span>
            Safe to spend
          </span>
          <Badge variant={s.confidence === 'good' ? 'secondary' : 'outline'}>
            {s.confidence === 'good' ? 'Commitments reserved' : 'Estimate — limited info'}
          </Badge>
        </CardDescription>
        <CardTitle className="pt-2">
          <span className="num block text-[34px] leading-none font-semibold tracking-tight sm:text-4xl">
            {formatTaka(s.recommended, { trimZeroDecimals: true })}
          </span>
          <span className="mt-2 block text-sm font-normal text-muted-foreground">
            about <span className="num font-medium text-foreground">{formatTaka(s.per_day, { trimZeroDecimals: true })}</span> a
            day for the next {s.days_left} day{s.days_left === 1 ? '' : 's'}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <ReserveBar s={s} />
        {limitedByBudget && (
          <p className="text-sm text-muted-foreground">
            Limited by your budget: your money allows {formatTaka(s.available, { trimZeroDecimals: true })}, but
            your flexible categories have {formatTaka(s.flexible_budget_left!, { trimZeroDecimals: true })} left.
          </p>
        )}
        {s.expected_income !== '0.00' && (
          <p className="text-sm text-muted-foreground">
            If expected income ({formatTaka(s.expected_income, { trimZeroDecimals: true })}) arrives:{' '}
            <Money value={s.available_if_expected_arrives} className="font-medium text-foreground" /> available. Not
            counted until received.
          </p>
        )}
        {s.notes.map((note) => (
          <p key={note} className="flex items-start gap-1.5 text-sm text-warning">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {note}
          </p>
        ))}

        <Button
          variant="ghost"
          size="sm"
          className="-ml-2 mt-auto self-start text-muted-foreground"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="safe-breakdown"
        >
          <ChevronDown className={open ? 'rotate-180 transition-transform duration-200' : 'transition-transform duration-200'} aria-hidden />
          How is this calculated?
        </Button>
        {open && (
          <dl id="safe-breakdown" className="animate-in space-y-1.5 rounded-lg border bg-surface-subtle p-3 text-sm duration-200 fade-in-0 slide-in-from-top-1">
            <Row label="Money in your wallets (excl. savings wallets)" value={s.spendable_balance} />
            <Row label={`Unpaid bills (${s.unpaid_bill_count})`} value={s.unpaid_bills} minus />
            <Row label="Savings still to set aside" value={s.savings_to_reserve} minus />
            <Row label="Essential budget still needed" value={s.essentials_to_reserve} minus />
            <div className="my-1 border-t" />
            <Row label="Available after commitments" value={s.available} strong />
            {s.flexible_budget_left !== null && (
              <Row label="Left in flexible budget categories" value={s.flexible_budget_left} />
            )}
            <p className="pt-1 text-xs text-muted-foreground">
              Safe to spend = the smaller of these two{s.flexible_budget_left === null ? ' (no budget yet, so only your money counts)' : ''}.
              Expected income is never counted until it actually arrives.
            </p>
            {!s.has_budget && (
              <Button asChild size="sm" variant="outline" className="mt-1">
                <Link to="/plan">Create a budget</Link>
              </Button>
            )}
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

function Row({ label, value, minus, strong }: { label: string; value: string; minus?: boolean; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 ${strong ? 'font-semibold' : ''}`}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={`num ${isNegative(value) ? 'text-destructive' : ''}`}>
        {minus && value !== '0.00' ? '− ' : ''}
        {formatTaka(value)}
      </dd>
    </div>
  )
}

type SafeToSpendData = NonNullable<ReturnType<typeof useSafeToSpend>['data']>

/**
 * Where the spendable money goes, as one bar: safe to spend vs. what's reserved.
 * Display only — every amount comes from the backend; widths are just proportions.
 */
function ReserveBar({ s }: { s: SafeToSpendData }) {
  const total = Number(s.spendable_balance)
  const parts = [
    { key: 'safe', label: 'Safe to spend', value: s.recommended, color: 'bg-primary' },
    { key: 'bills', label: 'Bills', value: s.unpaid_bills, color: 'bg-warning' },
    { key: 'savings', label: 'Savings', value: s.savings_to_reserve, color: 'bg-[var(--viz-series-1)]' },
    { key: 'essentials', label: 'Essentials', value: s.essentials_to_reserve, color: 'bg-foreground/30' },
  ].filter((p) => Number(p.value) > 0)
  if (!(total > 0) || parts.length < 2) return null

  return (
    <div className="space-y-2.5 pt-1">
      <div
        className="flex h-2 w-full gap-0.5 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`Of ${formatTaka(s.spendable_balance)} in your wallets: ${parts
          .map((p) => `${p.label} ${formatTaka(p.value, { trimZeroDecimals: true })}`)
          .join(', ')}`}
      >
        {parts.map((p) => (
          <span
            key={p.key}
            className={`${p.color} h-full first:rounded-l-full last:rounded-r-full`}
            style={{ width: `${Math.max(2, (Number(p.value) / total) * 100)}%` }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden>
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <span className={`${p.color} size-2 rounded-full`} />
            {p.label}
            <span className="num font-medium text-foreground">{formatTaka(p.value, { trimZeroDecimals: true })}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

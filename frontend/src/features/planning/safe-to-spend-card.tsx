import { ChevronDown, Info } from 'lucide-react'
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
    <Card className="border-primary">
      <CardHeader className="pb-0">
        <CardDescription className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[11px] font-semibold tracking-[0.14em] uppercase">Safe to spend this month</span>
          <Badge variant={s.confidence === 'good' ? 'secondary' : 'outline'}>
            {s.confidence === 'good' ? 'Commitments reserved' : 'Estimate, limited info'}
          </Badge>
        </CardDescription>
        <CardTitle className="space-y-1 pt-2">
          <span className="block font-display text-[56px] leading-[0.9] font-extrabold tracking-[-0.045em] text-primary">
            {formatTaka(s.recommended, { trimZeroDecimals: true })}
          </span>
          <span className="block text-sm font-normal text-muted-foreground">
            About {formatTaka(s.per_day, { trimZeroDecimals: true })} a day for the next {s.days_left} day{s.days_left === 1 ? '' : 's'}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {limitedByBudget && (
          <p className="text-sm text-muted-foreground">
            Limited by your budget: your money allows {formatTaka(s.available, { trimZeroDecimals: true })}, but
            your flexible categories have {formatTaka(s.flexible_budget_left!, { trimZeroDecimals: true })} left.
          </p>
        )}
        {s.expected_income !== '0.00' && (
          <p className="text-sm">
            <span className="text-muted-foreground">If expected income ({formatTaka(s.expected_income, { trimZeroDecimals: true })}) arrives: </span>
            <Money value={s.available_if_expected_arrives} className="font-medium" /> available. Not counted until received.
          </p>
        )}
        {s.notes.map((note) => (
          <p key={note} className="flex items-start gap-1.5 text-sm text-amber-700 dark:text-amber-400">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {note}
          </p>
        ))}

        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="safe-breakdown"
        >
          <ChevronDown className={open ? 'rotate-180 transition-transform' : 'transition-transform'} aria-hidden />
          How is this calculated?
        </Button>
        {open && (
          <dl id="safe-breakdown" className="space-y-1.5 rounded-lg bg-muted/60 p-3 text-sm">
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
      <dd className={`tabular-nums ${isNegative(value) ? 'text-destructive' : ''}`}>
        {minus && value !== '0.00' ? '− ' : ''}
        {formatTaka(value)}
      </dd>
    </div>
  )
}

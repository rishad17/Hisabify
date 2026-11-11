import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  BudgetVsActualChart,
  CategoryBreakdownChart,
  DailySpendingChart,
  ForecastChart,
  IncomeExpenseChart,
  MonthCompareChart,
} from '@/features/insights/charts'
import { currentMonth, formatMonth, shiftMonth } from '@/lib/dates'

export function InsightsPage() {
  const [month, setMonth] = useState(currentMonth())
  const isCurrent = month >= currentMonth()

  return (
    <div className="space-y-6">
      {/* One filter row above all charts — never a filter inside a chart card. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.02em] sm:text-[30px]">Insights</h1>
          <p className="text-sm text-muted-foreground">Where your money goes, and how it's changing.</p>
        </div>
        <div className="inline-flex items-center gap-0.5 rounded-lg border bg-card p-0.5 shadow-xs">
          <Button variant="ghost" size="icon-sm" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
            <ChevronLeft aria-hidden />
          </Button>
          <span className="min-w-32 text-center text-sm font-medium" aria-live="polite">{formatMonth(month)}</span>
          <Button variant="ghost" size="icon-sm" onClick={() => setMonth(shiftMonth(month, 1))} disabled={isCurrent} aria-label="Next month">
            <ChevronRight aria-hidden />
          </Button>
        </div>
      </div>

      {isCurrent && <ForecastChart />}

      <div className="grid gap-4 lg:grid-cols-2">
        <CategoryBreakdownChart month={month} />
        <DailySpendingChart month={month} />
        <MonthCompareChart month={month} />
        <BudgetVsActualChart month={month} />
      </div>
      <IncomeExpenseChart />
    </div>
  )
}

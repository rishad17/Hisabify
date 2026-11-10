import { AlertTriangle } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { CategoryIcon } from '@/components/category-icon'
import { useBreakdown, useCompare, useDaily, useMonthly } from '@/features/insights/api'
import {
  ANIMATE,
  AXIS_TICK,
  BAR_MAX,
  ChartCard,
  DataTable,
  Legend,
  num,
  TooltipBox,
  VIZ,
} from '@/features/insights/chart-parts'
import { useBudget } from '@/features/planning/api'
import { formatDayLabel, formatMonth } from '@/lib/dates'
import { compactTaka, formatTaka, isNegative } from '@/lib/money'

const t = (amount: string) => formatTaka(amount, { trimZeroDecimals: true })
const shortMonth = (m: string) => formatMonth(m).slice(0, 3) // "Nov" — full name is in the tooltip

// ------------------------------------------------------------------ where the money went

export function CategoryBreakdownChart({ month }: { month: string }) {
  const q = useBreakdown(month)
  const items = q.data?.items ?? []
  const data = items.map((i) => ({
    name: i.category?.name ?? `Other (${i.other_count})`,
    value: num(i.amount),
    amount: i.amount,
    share: i.share_percent,
  }))
  const height = Math.max(120, data.length * 34 + 16)

  return (
    <ChartCard
      title="Where your money went"
      description={`Spending by category · ${formatMonth(month)}`}
      headline={q.data && q.data.total !== '0.00' && <p className="text-2xl font-semibold">{t(q.data.total)}</p>}
      loading={q.isPending}
      error={q.error?.message}
      empty={items.length === 0}
      emptyText="No spending recorded this month."
      chart={
        <div style={{ height }} role="img" aria-label={`Bar chart of spending by category for ${formatMonth(month)}`}>
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
              <CartesianGrid horizontal={false} stroke={VIZ.grid} />
              <XAxis type="number" hide domain={[0, 'dataMax']} />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={AXIS_TICK}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: VIZ.cursor }}
                content={({ active, payload }) =>
                  active && payload?.[0] ? (
                    <TooltipBox
                      title={payload[0].payload.name}
                      rows={[{ label: `${payload[0].payload.share}% of spending`, value: t(payload[0].payload.amount) }]}
                    />
                  ) : null
                }
              />
              <Bar isAnimationActive={ANIMATE} dataKey="value" fill={VIZ.series1} radius={[0, 4, 4, 0]} maxBarSize={BAR_MAX}>
                <LabelList
                  dataKey="amount"
                  position="right"
                  formatter={(v) => t(String(v))}
                  style={{ fill: 'var(--foreground)', fontSize: 12 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      }
      table={
        <DataTable
          head={['Category', 'Amount', 'Share']}
          rows={items.map((i) => [
            i.category ? (
              <span className="flex items-center gap-2">
                <CategoryIcon name={i.category.icon} className="size-3.5 text-muted-foreground" />
                {i.category.name}
              </span>
            ) : (
              `Other (${i.other_count} categories)`
            ),
            formatTaka(i.amount),
            `${i.share_percent}%`,
          ])}
        />
      }
    />
  )
}

// ------------------------------------------------------------------ daily

export function DailySpendingChart({ month }: { month: string }) {
  const q = useDaily(month)
  const days = q.data?.days ?? []
  const data = days.map((d) => ({ day: Number(d.date.slice(8)), date: d.date, value: num(d.expense), amount: d.expense }))
  const avg = q.data ? num(q.data.average_daily_expense) : 0
  const empty = !q.data || q.data.total_expense === '0.00'

  return (
    <ChartCard
      title="Daily spending"
      description={
        q.data && !empty
          ? `Average ${t(q.data.average_daily_expense)} a day over ${q.data.days_counted} day${q.data.days_counted === 1 ? '' : 's'}`
          : formatMonth(month)
      }
      loading={q.isPending}
      error={q.error?.message}
      empty={empty}
      emptyText="No spending recorded this month."
      chart={
        <div className="h-56" role="img" aria-label={`Column chart of daily spending for ${formatMonth(month)}`}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={VIZ.grid} />
              <XAxis dataKey="day" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: VIZ.grid }} interval="preserveStartEnd" minTickGap={12} />
              <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} tickFormatter={compactTaka} allowDecimals={false} />
              <Tooltip
                cursor={{ fill: VIZ.cursor }}
                content={({ active, payload }) =>
                  active && payload?.[0] ? (
                    <TooltipBox title={formatDayLabel(payload[0].payload.date)} rows={[{ label: 'Spent', value: t(payload[0].payload.amount) }]} />
                  ) : null
                }
              />
              {avg > 0 && (
                <ReferenceLine
                  y={avg}
                  stroke={VIZ.muted}
                  strokeWidth={1}
                  label={{ value: 'avg', position: 'insideTopLeft', fill: VIZ.text, fontSize: 11 }}
                />
              )}
              <Bar isAnimationActive={ANIMATE} dataKey="value" fill={VIZ.series1} radius={[4, 4, 0, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      }
      table={
        <DataTable
          head={['Day', 'Spent', 'Received']}
          rows={[...days].reverse().map((d) => [formatDayLabel(d.date), formatTaka(d.expense), formatTaka(d.income)])}
        />
      }
    />
  )
}

// ------------------------------------------------------------------ income vs expense

export function IncomeExpenseChart() {
  const q = useMonthly(6)
  const months = q.data?.months ?? []
  const data = months.map((m) => ({
    label: shortMonth(m.month) + (m.partial ? '*' : ''),
    month: m.month,
    income: num(m.income),
    expense: num(m.expense),
    raw: m,
  }))
  const empty = months.every((m) => m.income === '0.00' && m.expense === '0.00')

  return (
    <ChartCard
      title="Income vs expenses"
      description="Last 6 months · transfers between your wallets are not counted"
      loading={q.isPending}
      error={q.error?.message}
      empty={empty}
      chart={
        <>
          <Legend items={[{ label: 'Income', color: VIZ.series1 }, { label: 'Expenses', color: VIZ.series2 }]} />
          <div className="h-56" role="img" aria-label="Grouped column chart of monthly income and expenses for the last 6 months">
            <ResponsiveContainer>
              <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="28%">
                <CartesianGrid vertical={false} stroke={VIZ.grid} />
                <XAxis dataKey="label" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: VIZ.grid }} />
                <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} tickFormatter={compactTaka} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: VIZ.cursor }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null
                    const m = payload[0].payload.raw as (typeof months)[number]
                    return (
                      <TooltipBox
                        title={formatMonth(m.month) + (m.partial ? ' (so far)' : '')}
                        rows={[
                          { label: 'Income', value: t(m.income), color: VIZ.series1 },
                          { label: 'Expenses', value: t(m.expense), color: VIZ.series2 },
                          { label: 'Net', value: (isNegative(m.net) ? '' : '+') + t(m.net) },
                        ]}
                      />
                    )
                  }}
                />
                <Bar isAnimationActive={ANIMATE} dataKey="income" fill={VIZ.series1} radius={[4, 4, 0, 0]} maxBarSize={BAR_MAX} />
                <Bar isAnimationActive={ANIMATE} dataKey="expense" fill={VIZ.series2} radius={[4, 4, 0, 0]} maxBarSize={BAR_MAX} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">* current month, still in progress</p>
        </>
      }
      table={
        <DataTable
          head={['Month', 'Income', 'Expenses', 'Net']}
          rows={[...months].reverse().map((m) => [
            formatMonth(m.month) + (m.partial ? ' (so far)' : ''),
            formatTaka(m.income),
            formatTaka(m.expense),
            formatTaka(m.net),
          ])}
        />
      }
    />
  )
}

// ------------------------------------------------------------------ this vs last month

export function MonthCompareChart({ month }: { month: string }) {
  const q = useCompare(month)
  const c = q.data
  const items = c?.items.slice(0, 8) ?? []
  const data = items.map((i) => ({ name: i.category.name, current: num(i.current), previous: num(i.previous), raw: i }))
  const height = Math.max(140, data.length * 44 + 16)
  const up = c && !isNegative(c.change) && c.change !== '0.00'

  return (
    <ChartCard
      title="Compared with last month"
      description={c ? `${c.current_label} vs ${c.previous_label}${c.partial ? ' (same days, for a fair comparison)' : ''}` : undefined}
      headline={
        c && c.items.length > 0 && (
          <p className="text-sm">
            <span className="text-2xl font-semibold">{t(c.current_total)}</span>{' '}
            <span className="text-muted-foreground">
              {c.change === '0.00' ? 'same as' : up ? `${t(c.change)} more than` : `${t(c.change.slice(1))} less than`} {t(c.previous_total)}
            </span>
          </p>
        )
      }
      loading={q.isPending}
      error={q.error?.message}
      empty={items.length === 0}
      emptyText="No spending in either period yet."
      chart={
        <>
          <Legend items={[{ label: c?.current_label ?? 'This month', color: VIZ.series1 }, { label: c?.previous_label ?? 'Last month', color: VIZ.muted }]} />
          <div style={{ height }} role="img" aria-label="Paired bar chart comparing category spending with the previous month">
            <ResponsiveContainer>
              <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barGap={2}>
                <CartesianGrid horizontal={false} stroke={VIZ.grid} />
                <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={compactTaka} allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={120} tick={AXIS_TICK} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: VIZ.cursor }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null
                    const i = payload[0].payload.raw as (typeof items)[number]
                    return (
                      <TooltipBox
                        title={i.category.name}
                        rows={[
                          { label: c!.current_label, value: t(i.current), color: VIZ.series1 },
                          { label: c!.previous_label, value: t(i.previous), color: VIZ.muted },
                          { label: 'Change', value: (isNegative(i.change) ? '' : '+') + t(i.change) },
                        ]}
                      />
                    )
                  }}
                />
                <Bar isAnimationActive={ANIMATE} dataKey="current" fill={VIZ.series1} radius={[0, 4, 4, 0]} maxBarSize={14} />
                <Bar isAnimationActive={ANIMATE} dataKey="previous" fill={VIZ.muted} radius={[0, 4, 4, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      }
      table={
        <DataTable
          head={['Category', c?.current_label ?? 'This', c?.previous_label ?? 'Previous', 'Change']}
          rows={(c?.items ?? []).map((i) => [
            i.category.name,
            formatTaka(i.current),
            formatTaka(i.previous),
            (isNegative(i.change) ? '' : '+') + formatTaka(i.change),
          ])}
        />
      }
    />
  )
}

// ------------------------------------------------------------------ budget vs actual

export function BudgetVsActualChart({ month }: { month: string }) {
  const q = useBudget(month)
  const b = q.data
  const items = b?.items ?? []
  const data = items.map((i) => ({
    name: i.category.name,
    budget: num(i.amount),
    spent: num(i.spent),
    over: isNegative(i.remaining),
    raw: i,
  }))
  const height = Math.max(140, data.length * 44 + 16)
  const overCount = data.filter((d) => d.over).length

  return (
    <ChartCard
      title="Budget vs actual"
      description={b ? `Spent ${t(b.total_spent)} of ${t(b.total_budget)} budgeted` : formatMonth(month)}
      headline={
        overCount > 0 && (
          <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
            <AlertTriangle className="size-4" aria-hidden /> {overCount} categor{overCount === 1 ? 'y is' : 'ies are'} over budget
          </p>
        )
      }
      loading={q.isPending}
      error={q.error?.message}
      empty={!b || items.length === 0}
      emptyText="No budget for this month. Create one on the Plan page."
      chart={
        <>
          <Legend items={[{ label: 'Spent', color: VIZ.series1 }, { label: 'Budget', color: VIZ.muted }]} />
          <div style={{ height }} role="img" aria-label="Paired bar chart of spending against budget per category">
            <ResponsiveContainer>
              <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barGap={2}>
                <CartesianGrid horizontal={false} stroke={VIZ.grid} />
                <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={compactTaka} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  tickLine={false}
                  axisLine={false}
                  tick={({ x, y, payload }) => {
                    const row = data.find((d) => d.name === payload.value)
                    return (
                      <text x={x} y={y} dy={4} textAnchor="end" fontSize={12} fill="var(--muted-foreground)">
                        {row?.over ? '⚠ ' : ''}
                        {payload.value}
                      </text>
                    )
                  }}
                />
                <Tooltip
                  cursor={{ fill: VIZ.cursor }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null
                    const i = payload[0].payload.raw as (typeof items)[number]
                    const over = isNegative(i.remaining)
                    return (
                      <TooltipBox
                        title={i.category.name}
                        rows={[
                          { label: 'Spent', value: t(i.spent), color: VIZ.series1 },
                          { label: 'Budget', value: t(i.amount), color: VIZ.muted },
                          { label: over ? '⚠ Over by' : 'Left', value: t(over ? i.remaining.slice(1) : i.remaining) },
                        ]}
                      />
                    )
                  }}
                />
                <Bar isAnimationActive={ANIMATE} dataKey="spent" fill={VIZ.series1} radius={[0, 4, 4, 0]} maxBarSize={14} />
                <Bar isAnimationActive={ANIMATE} dataKey="budget" fill={VIZ.muted} radius={[0, 4, 4, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      }
      table={
        <DataTable
          head={['Category', 'Budget', 'Spent', 'Left']}
          rows={items.map((i) => [
            i.category.name,
            formatTaka(i.amount),
            formatTaka(i.spent),
            isNegative(i.remaining) ? `⚠ Over ${formatTaka(i.remaining.slice(1))}` : formatTaka(i.remaining),
          ])}
        />
      }
    />
  )
}

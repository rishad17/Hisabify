/**
 * Shared chart building blocks so every chart follows the same rules:
 *  - series colours come from CSS tokens (--viz-*), validated for colour-blindness
 *  - text uses text tokens, never the series colour
 *  - hairline solid gridlines, one y-axis, thin bars with 4px rounded data-ends
 *  - every chart has a table view (values never live only in a tooltip)
 */
import { BarChart3, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export const VIZ = {
  series1: 'var(--viz-series-1)',
  series2: 'var(--viz-series-2)',
  muted: 'var(--viz-muted)',
  grid: 'var(--viz-grid)',
  cursor: 'var(--viz-cursor)',
  text: 'var(--muted-foreground)',
} as const

export const AXIS_TICK = { fill: VIZ.text, fontSize: 12 }
export const BAR_MAX = 20 // px — bars never fill the whole band

/** Respect the OS "reduce motion" setting: no growing-bar animation for those users. */
export const ANIMATE =
  typeof window === 'undefined' || !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Decimal string → number, for chart GEOMETRY only. Labels always use the exact string. */
export const num = (amount: string) => Number.parseFloat(amount)

export function ChartCard({
  title,
  description,
  headline,
  loading,
  error,
  empty,
  emptyText = 'No data yet for this period.',
  chart,
  table,
  action,
}: {
  title: string
  description?: ReactNode
  headline?: ReactNode
  loading: boolean
  error?: string | null
  empty: boolean
  emptyText?: string
  chart: ReactNode
  table: ReactNode
  action?: ReactNode
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  return (
    // min-w-0: lets the card shrink inside CSS grid so ResponsiveContainer can't overflow on phones.
    <Card className="min-w-0 gap-3">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-base">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {action}
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => setView((v) => (v === 'chart' ? 'table' : 'chart'))}
              aria-label={view === 'chart' ? `Show ${title} as a table` : `Show ${title} as a chart`}
              aria-pressed={view === 'table'}
              title={view === 'chart' ? 'Table view' : 'Chart view'}
            >
              {view === 'chart' ? <Table2 aria-hidden /> : <BarChart3 aria-hidden />}
            </Button>
          </div>
        </div>
        {headline && <div className="pt-1">{headline}</div>}
      </CardHeader>
      <CardContent className="min-w-0">
        {loading ? (
          <Skeleton className="h-56 w-full" />
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : empty ? (
          <p className="flex h-40 items-center justify-center text-center text-sm text-muted-foreground">{emptyText}</p>
        ) : view === 'chart' ? (
          chart
        ) : (
          <div className="max-h-80 overflow-auto">{table}</div>
        )}
      </CardContent>
    </Card>
  )
}

export function DataTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <table className="w-full text-sm">
      <thead className="sticky top-0 bg-card">
        <tr className="border-b text-left text-xs text-muted-foreground">
          {head.map((h, i) => (
            <th key={h} className={`py-1.5 font-medium ${i > 0 ? 'text-right' : ''}`}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((cells, r) => (
          <tr key={r} className="border-b last:border-0">
            {cells.map((c, i) => (
              <td key={i} className={`py-1.5 ${i > 0 ? 'text-right tabular-nums' : ''}`}>{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Legend for ≥ 2 series: swatch beside text; the text itself stays in text colour. */
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: i.color }} aria-hidden />
          {i.label}
        </li>
      ))}
    </ul>
  )
}

type TipRow = { label: string; value: string; color?: string; note?: string }

/** Tooltip body. Recharts passes payload; each chart maps it to rows. */
export function TooltipBox({ title, rows }: { title: string; rows: TipRow[] }) {
  return (
    <div className="min-w-36 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="mb-1 font-medium">{title}</p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            {r.color && <span className="inline-block size-2 rounded-sm" style={{ background: r.color }} aria-hidden />}
            {r.label}
          </span>
          <span className="font-medium tabular-nums">{r.value}</span>
        </div>
      ))}
      {rows.map((r) => r.note && <p key={`${r.label}-note`} className="mt-1 text-muted-foreground">{r.note}</p>)}
    </div>
  )
}

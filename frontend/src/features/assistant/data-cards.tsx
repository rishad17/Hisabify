import { ChevronDown, Database } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import type { ToolUse } from '@/features/assistant/api'
import { SimulationResult, type Simulation } from '@/features/planning/simulation-result'
import { formatTaka } from '@/lib/money'

const t = (a: unknown) => formatTaka(String(a), { trimZeroDecimals: true })
type R = Record<string, unknown>

const TOOL_LABEL: Record<string, string> = {
  get_balances: 'Wallet balances',
  get_spending: 'Spending',
  compare_months: 'Month comparison',
  get_budget_status: 'Budget status',
  get_safe_to_spend: 'Safe to spend',
  simulate_purchase: 'Purchase simulation',
  get_bills: 'Bills',
  search_transactions: 'Transactions',
  get_categories: 'Categories',
}

/**
 * The exact data the assistant used, straight from the backend tools. The answer text is
 * the model's wording; these cards are the source of truth the user can check it against.
 */
export function DataCards({ tools }: { tools: ToolUse[] }) {
  const [open, setOpen] = useState(false)
  const useful = tools.filter((u) => !('error' in u.result) && u.name !== 'get_categories')
  const sims = useful.filter((u) => u.name === 'simulate_purchase')
  const rest = useful.filter((u) => u.name !== 'simulate_purchase')
  if (useful.length === 0) return null

  return (
    <div className="space-y-2">
      {/* Simulations are the answer itself, so they're always shown. */}
      {sims.map((u, i) => <SimulationResult key={i} sim={u.result as unknown as Simulation} />)}
      {rest.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <Database className="size-3.5" aria-hidden />
            Data used ({rest.map((u) => TOOL_LABEL[u.name] ?? u.name).join(', ')})
            <ChevronDown className={`size-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {open && (
            <div className="grid gap-2 sm:grid-cols-2">
              {rest.map((u, i) => (
                <div key={i} className="rounded-lg border bg-muted/40 p-3 text-xs">
                  <p className="mb-1.5 font-medium text-foreground">{TOOL_LABEL[u.name] ?? u.name}</p>
                  <ToolCard name={u.name} r={u.result} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Rows({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="space-y-0.5">
      {rows.map(([k, v], i) => (
        <div key={i} className="flex justify-between gap-3">
          <dt className="truncate text-muted-foreground">{k}</dt>
          <dd className="font-medium tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function ToolCard({ name, r }: { name: string; r: R }) {
  switch (name) {
    case 'get_balances': {
      const wallets = (r.wallets as { name: string; balance: string }[]) ?? []
      return <Rows rows={[...wallets.map((w) => [w.name, t(w.balance)] as [string, string]), ['Total', t(r.total)]]} />
    }
    case 'get_spending': {
      const cats = (r.by_category as { category: string; amount: string }[]) ?? []
      return (
        <>
          <p className="mb-1 text-muted-foreground">{String(r.period)}</p>
          <Rows rows={[['Spent', t(r.total_expense)], ['Received', t(r.total_income)], ...cats.slice(0, 5).map((c) => [c.category, t(c.amount)] as [string, string])]} />
        </>
      )
    }
    case 'compare_months':
      return <Rows rows={[[String(r.current_label), t(r.current_total)], [String(r.previous_label), t(r.previous_total)], ['Change', t(r.change)]]} />
    case 'get_safe_to_spend':
      return (
        <Rows
          rows={[
            ['Safe to spend', t(r.recommended)],
            ['Per day', t(r.per_day)],
            ...(r.this_week_allowance !== undefined ? [['This week', t(r.this_week_allowance)] as [string, string]] : []),
            ['Unpaid bills', t(r.unpaid_bills)],
            ['Savings to set aside', t(r.savings_to_reserve)],
          ]}
        />
      )
    case 'get_budget_status': {
      const items = (r.items as { category: string; spent: string; budget: string }[]) ?? []
      if (!items.length) return <p className="text-muted-foreground">No budget for this month.</p>
      return <Rows rows={items.slice(0, 6).map((i) => [i.category, `${t(i.spent)} / ${t(i.budget)}`] as [string, string])} />
    }
    case 'search_transactions': {
      const txs = (r.transactions as { date: string; description: string | null; category: string | null; amount: string }[]) ?? []
      if (!txs.length) return <p className="text-muted-foreground">No matching transactions.</p>
      return <Rows rows={txs.slice(0, 6).map((x) => [`${x.date} · ${x.description ?? x.category ?? ''}`, t(x.amount)] as [string, string])} />
    }
    case 'get_bills': {
      const bills = (r.bills as { name: string; amount: string; paid: boolean }[]) ?? []
      return <Rows rows={bills.map((b) => [`${b.name}${b.paid ? ' ✓' : ''}`, t(b.amount)] as [string, string])} />
    }
    default:
      return null
  }
}

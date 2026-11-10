import { AlertTriangle, CircleCheck, CircleX, Info, PiggyBank } from 'lucide-react'

import { formatTaka, isNegative } from '@/lib/money'
import { cn } from '@/lib/utils'

export type Simulation = {
  amount: string
  verdict: 'affordable' | 'likely_affordable' | 'over_budget' | 'cuts_into_savings' | 'not_affordable'
  available_before?: string
  available_after: string
  savings_target_left?: string
  savings_shortfall: string
  commitments_shortfall?: string
  category_name: string | null
  category_remaining_after: string | null
  max_without_touching_savings?: string
  reasons: string[]
  alternatives: string[]
}

// Status = icon + label + colour (never colour alone).
const VERDICT = {
  affordable: { label: 'Affordable', icon: CircleCheck, tone: 'text-emerald-700 dark:text-emerald-400 border-emerald-600/30 bg-emerald-500/5' },
  likely_affordable: { label: 'Looks affordable (estimate)', icon: Info, tone: 'text-emerald-700 dark:text-emerald-400 border-emerald-600/30 bg-emerald-500/5' },
  over_budget: { label: 'Affordable, but over budget', icon: AlertTriangle, tone: 'text-amber-700 dark:text-amber-400 border-amber-500/40 bg-amber-500/5' },
  cuts_into_savings: { label: 'Cuts into your savings', icon: PiggyBank, tone: 'text-amber-700 dark:text-amber-400 border-amber-500/40 bg-amber-500/5' },
  not_affordable: { label: 'Not affordable this month', icon: CircleX, tone: 'text-destructive border-destructive/40 bg-destructive/5' },
} as const

const t = (a: string) => formatTaka(a, { trimZeroDecimals: true })

/** Read-only result of a what-if purchase. Nothing was recorded. */
export function SimulationResult({ sim }: { sim: Simulation }) {
  const v = VERDICT[sim.verdict]
  return (
    <div className={cn('space-y-2 rounded-lg border p-3 text-sm', v.tone)}>
      <p className="flex items-center gap-1.5 font-semibold">
        <v.icon className="size-4" aria-hidden /> {v.label} · {t(sim.amount)}
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-foreground">
        <dt className="text-muted-foreground">Free after buying</dt>
        <dd className={cn('text-right font-medium', isNegative(sim.available_after) && 'text-destructive')}>{t(sim.available_after)}</dd>
        {sim.savings_shortfall !== '0.00' && (
          <>
            <dt className="text-muted-foreground">Savings you'd lose</dt>
            <dd className="text-right font-medium">{t(sim.savings_shortfall)}</dd>
          </>
        )}
        {sim.category_name && sim.category_remaining_after !== null && (
          <>
            <dt className="text-muted-foreground">{sim.category_name} budget after</dt>
            <dd className={cn('text-right font-medium', isNegative(sim.category_remaining_after) && 'text-destructive')}>
              {t(sim.category_remaining_after)}
            </dd>
          </>
        )}
      </dl>
      <ul className="list-disc space-y-0.5 pl-5 text-foreground">
        {sim.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
      {sim.alternatives.length > 0 && (
        <div className="text-foreground">
          <p className="text-xs font-medium text-muted-foreground uppercase">Options</p>
          <ul className="list-disc space-y-0.5 pl-5">
            {sim.alternatives.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted-foreground">Simulation only. Nothing was recorded.</p>
    </div>
  )
}

import { ArrowRight, Check, ChevronDown, History, Info, Loader2, Wand2, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useAdjustmentHistory,
  useDecideAdjustment,
  useSuggestAdjustment,
  type Adjustment,
} from '@/features/planning/api'
import { ApiError } from '@/lib/api'
import { formatDayLabel } from '@/lib/dates'
import { formatTaka } from '@/lib/money'

const t = (a: string) => formatTaka(a, { trimZeroDecimals: true })
const BY = { system: 'Suggested by the app', user: 'Your edit', ai: 'Suggested by AI' } as const

/**
 * Adaptive budget: the app proposes moving money between categories; NOTHING changes
 * until the user approves. Every proposal, approval, rejection and manual edit is kept.
 */
export function AdjustmentsPanel({ month, isCurrentMonth }: { month: string; isCurrentMonth: boolean }) {
  const history = useAdjustmentHistory(month)
  const suggestMut = useSuggestAdjustment()
  const decide = useDecideAdjustment()
  const [message, setMessage] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const open = history.data?.find((a) => a.status === 'proposed')
  const past = history.data?.filter((a) => a.status !== 'proposed') ?? []

  async function suggest() {
    setMessage(null)
    try {
      const r = await suggestMut.mutateAsync()
      if (!r.suggestion) setMessage(r.message)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not create a suggestion.')
    }
  }

  async function onDecide(adj: Adjustment, approve: boolean) {
    try {
      await decide.mutateAsync({ id: adj.id, approve })
      toast.success(approve ? 'Budget updated' : 'Suggestion dismissed')
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Something went wrong.')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Wand2 className="size-4" aria-hidden /> Keep your budget on track
        </CardTitle>
        <CardDescription>
          The app can suggest moving money from categories with room to ones heading over. Your budget only changes
          if you approve.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {open ? (
          <div className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-3">
            <p className="text-sm">{open.reason}</p>
            <ChangesTable adj={open} />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => onDecide(open, true)} disabled={decide.isPending}>
                {decide.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Check aria-hidden />} Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => onDecide(open, false)} disabled={decide.isPending}>
                <X aria-hidden /> Dismiss
              </Button>
            </div>
          </div>
        ) : (
          isCurrentMonth && (
            <Button variant="outline" size="sm" onClick={suggest} disabled={suggestMut.isPending}>
              {suggestMut.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Wand2 aria-hidden />}
              Check & suggest changes
            </Button>
          )
        )}
        {message && (
          <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {message}
          </p>
        )}

        {past.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setShowHistory((s) => !s)}
              aria-expanded={showHistory}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <History className="size-4" aria-hidden /> Change history ({past.length})
              <ChevronDown className={`size-4 transition-transform ${showHistory ? 'rotate-180' : ''}`} aria-hidden />
            </button>
            {showHistory && (
              <ul className="mt-2 space-y-3">
                {past.map((a) => (
                  <li key={a.id} className="space-y-1.5 rounded-lg border p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={a.status === 'approved' ? 'secondary' : 'outline'}>
                        {a.status === 'approved' ? 'Applied' : 'Dismissed'}
                      </Badge>
                      <span className="text-muted-foreground">
                        {BY[a.proposed_by]} · {formatDayLabel((a.decided_at ?? a.created_at).slice(0, 10))}
                      </span>
                    </div>
                    <ChangesTable adj={a} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ChangesTable({ adj }: { adj: Adjustment }) {
  return (
    <ul className="space-y-1 text-sm">
      {adj.changes.map((c) => (
        <li key={c.category_id} className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate">{c.category_name}</span>
          <span className="tabular-nums text-muted-foreground">{t(c.old)}</span>
          <ArrowRight className="size-3.5 text-muted-foreground" aria-label="becomes" />
          <span className="font-medium tabular-nums">{t(c.new)}</span>
        </li>
      ))}
    </ul>
  )
}

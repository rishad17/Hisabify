import { AlertTriangle, ArrowRight, CircleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useAlerts } from '@/features/planning/api'
import { cn } from '@/lib/utils'

/** Budget warnings (shown only when there are any). Icon + label, never colour alone. */
export function BudgetAlerts() {
  const q = useAlerts()
  if (!q.data || q.data.length === 0) return null
  const critical = q.data.some((a) => a.severity === 'critical')

  return (
    <section
      role="region"
      aria-label="Budget warnings"
      className={cn(
        'relative overflow-hidden rounded-xl border bg-card shadow-card',
        critical ? 'border-destructive/25' : 'border-warning/30',
      )}
    >
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-1', critical ? 'bg-destructive' : 'bg-warning')} />
      <div className="flex flex-col gap-3 py-3.5 pr-4 pl-5 sm:flex-row sm:items-center sm:justify-between">
        <ul className="min-w-0 space-y-1.5">
          {q.data.map((a) => (
            <li key={`${a.category.id}-${a.kind}`} className="flex items-start gap-2.5 text-sm">
              {a.severity === 'critical' ? (
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-label="Over budget" />
              ) : (
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-label="Warning" />
              )}
              <span className="text-pretty">{a.message}</span>
            </li>
          ))}
        </ul>
        <Button asChild size="sm" variant="outline" className="shrink-0 self-start sm:self-center">
          <Link to="/plan">
            Review budget <ArrowRight aria-hidden />
          </Link>
        </Button>
      </div>
    </section>
  )
}

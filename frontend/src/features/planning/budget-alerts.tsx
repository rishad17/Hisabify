import { AlertTriangle, CircleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAlerts } from '@/features/planning/api'

/** Budget warnings (shown only when there are any). Icon + label, never colour alone. */
export function BudgetAlerts() {
  const q = useAlerts()
  if (!q.data || q.data.length === 0) return null

  return (
    <Card className="border-amber-500" role="region" aria-label="Budget warnings">
      <CardContent className="space-y-3">
        <ul className="space-y-1.5">
          {q.data.map((a) => (
            <li key={`${a.category.id}-${a.kind}`} className="flex items-start gap-2 text-sm">
              {a.severity === 'critical' ? (
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-label="Over budget" />
              ) : (
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-label="Warning" />
              )}
              <span>{a.message}</span>
            </li>
          ))}
        </ul>
        <Button asChild size="sm" variant="outline">
          <Link to="/plan">Review my budget</Link>
        </Button>
      </CardContent>
    </Card>
  )
}

import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** One consistent "nothing here yet" block: icon tile, title, hint and an optional action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card/60 px-6 py-12 text-center',
        className,
      )}
    >
      <span
        className="flex size-12 items-center justify-center rounded-2xl bg-accent text-xl text-primary ring-8 ring-accent/40 [&_svg]:size-5"
        aria-hidden
      >
        {icon}
      </span>
      <div className="space-y-1">
        <p className="font-semibold tracking-tight">{title}</p>
        {description && <p className="mx-auto max-w-sm text-sm text-pretty text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  )
}

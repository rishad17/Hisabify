import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** The TakaWise mark: a ৳ in a rounded emerald tile with a small gold "coin" spark. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative inline-flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-hero-from to-hero-to text-[17px] font-bold text-white shadow-sm ring-1 ring-black/5',
        className,
      )}
    >
      ৳
      <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-gold ring-2 ring-background" />
    </span>
  )
}

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      {!compact && (
        <span className="text-[17px] font-semibold tracking-tight">
          TakaWise <span className="text-primary">AI</span>
        </span>
      )}
    </span>
  )
}

/** Consistent page title row: title, optional subtitle, actions on the right. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

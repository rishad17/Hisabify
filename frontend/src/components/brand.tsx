import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * Wordmark: type-led, editorial. "Hisab" (হিসাব, accounts) in ink, "ify" in green.
 * No app-icon tile: the brand is the name.
 */
export function Logo({ className, size = 'md' }: { className?: string; size?: 'md' | 'lg' }) {
  return (
    <span
      className={cn(
        'font-display font-extrabold tracking-[-0.04em]',
        size === 'lg' ? 'text-[28px]' : 'text-[22px]',
        className,
      )}
    >
      Hisab<span className="text-primary">ify</span>
    </span>
  )
}

/** Page title in the display face, large and tight, with an optional kicker above. */
export function PageHeader({
  title,
  description,
  actions,
  kicker,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  kicker?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 space-y-2">
        {kicker && <Kicker>{kicker}</Kicker>}
        <h1 className="text-[34px] leading-[1.05] font-bold sm:text-5xl">{title}</h1>
        {description && <p className="max-w-xl text-[15px] text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/** Small uppercase label used above sections and figures. */
export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn('text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase', className)}>
      {children}
    </p>
  )
}

import { cn } from '@/lib/utils'
import { formatTaka, isNegative } from '@/lib/money'
import type { Transaction } from '@/features/ledger/api'

/** Signed, colored amount for a transaction row. Color is never the only signal: a sign
 * (+ / −) or arrow accompanies it, for color-blind users. */
export function TransactionAmount({ tx, className }: { tx: Transaction; className?: string }) {
  let text: string
  let tone: string
  switch (tx.type) {
    case 'expense':
      text = formatTaka(`-${tx.amount}`)
      tone = 'text-foreground'
      break
    case 'income':
      text = formatTaka(tx.amount, { showPlus: true })
      tone = 'text-emerald-700 dark:text-emerald-400'
      break
    case 'transfer':
      text = formatTaka(tx.amount)
      tone = 'text-muted-foreground'
      break
    default: // adjustment (already signed)
      text = formatTaka(tx.amount, { showPlus: true })
      tone = isNegative(tx.amount) ? 'text-foreground' : 'text-emerald-700 dark:text-emerald-400'
  }
  return <span className={cn('font-medium tabular-nums', tone, className)}>{text}</span>
}

/**
 * Headline figure in the display face: "৳35,990" large, ".50" small and raised.
 * Proportional digits on purpose (tabular figures look gappy at this size).
 */
export function BigMoney({ value, className }: { value: string; className?: string }) {
  const text = formatTaka(value)
  const dot = text.lastIndexOf('.')
  const whole = dot === -1 ? text : text.slice(0, dot)
  const cents = dot === -1 ? '' : text.slice(dot + 1)
  return (
    <p className={cn('font-display leading-[0.9] font-extrabold tracking-[-0.045em]', isNegative(value) && 'text-destructive', className)}>
      {whole}
      {cents && cents !== '00' && <span className="ml-1 align-top text-[0.3em] font-bold tracking-normal text-muted-foreground">.{cents}</span>}
    </p>
  )
}

/** A plain balance/total; negative values get a warning color. */
export function Money({ value, className }: { value: string; className?: string }) {
  return (
    <span className={cn('tabular-nums', isNegative(value) && 'text-destructive', className)}>
      {formatTaka(value)}
    </span>
  )
}

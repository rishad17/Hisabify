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
      tone = 'text-success'
      break
    case 'transfer':
      text = formatTaka(tx.amount)
      tone = 'text-muted-foreground'
      break
    default: // adjustment (already signed)
      text = formatTaka(tx.amount, { showPlus: true })
      tone = isNegative(tx.amount) ? 'text-foreground' : 'text-success'
  }
  return <span className={cn('num font-medium', tone, className)}>{text}</span>
}

/** A plain balance/total; negative values get a warning color. */
export function Money({ value, className }: { value: string; className?: string }) {
  return (
    <span className={cn('num', isNegative(value) && 'text-destructive', className)}>
      {formatTaka(value)}
    </span>
  )
}

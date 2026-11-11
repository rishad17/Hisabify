import { Banknote, Landmark, PiggyBank, Smartphone, WalletMinimal, type LucideIcon } from 'lucide-react'

import type { WalletType } from '@/features/ledger/api'

export const WALLET_TYPES: { value: WalletType; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'bkash', label: 'bKash' },
  { value: 'nagad', label: 'Nagad' },
  { value: 'rocket', label: 'Rocket' },
  { value: 'bank', label: 'Bank account' },
  { value: 'savings', label: 'Savings' },
  { value: 'other', label: 'Other' },
]

const ICONS: Record<WalletType, LucideIcon> = {
  cash: Banknote,
  bkash: Smartphone,
  nagad: Smartphone,
  rocket: Smartphone,
  bank: Landmark,
  savings: PiggyBank,
  other: WalletMinimal,
}

export function WalletIcon({ type, className }: { type: WalletType; className?: string }) {
  const Icon = ICONS[type] ?? WalletMinimal
  return <Icon className={className} aria-hidden />
}

/** Icon-tile colours per wallet type (a small nod to each service's colour). */
const TONES: Record<WalletType, string> = {
  cash: 'bg-accent text-primary',
  bkash: 'bg-[#e2136e]/10 text-[#b80f59] dark:bg-[#e2136e]/15 dark:text-[#ff6fa9]',
  nagad: 'bg-[#f6921e]/12 text-[#a85a06] dark:bg-[#f6921e]/15 dark:text-[#ffb35f]',
  rocket: 'bg-[#8c3494]/10 text-[#7a2d82] dark:bg-[#8c3494]/20 dark:text-[#d99be0]',
  bank: 'bg-[var(--viz-series-1)]/10 text-[var(--viz-series-1)]',
  savings: 'bg-gold/15 text-[#8a5f00] dark:text-gold',
  other: 'bg-muted text-foreground/70',
}

export function walletTone(type: WalletType): string {
  return TONES[type] ?? TONES.other
}

export function walletTypeLabel(type: WalletType): string {
  return WALLET_TYPES.find((t) => t.value === type)?.label ?? type
}

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

export function walletTypeLabel(type: WalletType): string {
  return WALLET_TYPES.find((t) => t.value === type)?.label ?? type
}

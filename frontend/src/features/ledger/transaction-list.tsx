import { ArrowLeftRight, Ellipsis, Mic, Pencil, Scale, Trash2, Type } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { CategoryIcon } from '@/components/category-icon'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useVoidTransaction, type Transaction } from '@/features/ledger/api'
import { TransactionAmount } from '@/features/ledger/amount'
import { TransactionFormDialog } from '@/features/ledger/transaction-form-dialog'
import { ApiError } from '@/lib/api'
import { formatDayLabel } from '@/lib/dates'
import { formatTaka } from '@/lib/money'

function title(tx: Transaction): string {
  if (tx.description) return tx.description
  if (tx.type === 'transfer') return 'Transfer'
  if (tx.type === 'adjustment') return 'Balance correction'
  return tx.category?.name ?? 'Transaction'
}

function subtitle(tx: Transaction): string {
  if (tx.type === 'transfer') return `${tx.wallet_name} → ${tx.to_wallet_name}`
  if (tx.type === 'adjustment') return tx.wallet_name
  const parts = [tx.description ? tx.category?.name : null, tx.wallet_name].filter(Boolean)
  return parts.join(' · ')
}

function RowIcon({ tx }: { tx: Transaction }) {
  const className = 'size-4'
  if (tx.type === 'transfer') return <ArrowLeftRight className={className} aria-hidden />
  if (tx.type === 'adjustment') return <Scale className={className} aria-hidden />
  return <CategoryIcon name={tx.category?.icon ?? null} className={className} />
}

/** Groups transactions by day and renders them with edit/delete actions. */
export function TransactionList({ items, groupByDay = true }: { items: Transaction[]; groupByDay?: boolean }) {
  const [editing, setEditing] = useState<Transaction | undefined>()
  const [deleting, setDeleting] = useState<Transaction | undefined>()
  const voidTx = useVoidTransaction()

  const groups: { day: string; items: Transaction[] }[] = []
  for (const tx of items) {
    const last = groups.at(-1)
    if (groupByDay && last?.day === tx.occurred_on) last.items.push(tx)
    else groups.push({ day: tx.occurred_on, items: [tx] })
  }

  async function confirmDelete() {
    if (!deleting) return
    try {
      await voidTx.mutateAsync(deleting.id)
      toast.success('Transaction deleted')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not delete. Try again.')
    } finally {
      setDeleting(undefined)
    }
  }

  return (
    <>
      <div className="space-y-4">
        {groups.map((group, gi) => (
          <section key={`${group.day}-${gi}`} aria-label={formatDayLabel(group.day)}>
            {groupByDay && (
              <h3 className="mb-1 px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {formatDayLabel(group.day)}
              </h3>
            )}
            <ul className="divide-y rounded-lg border bg-card">
              {group.items.map((tx) => (
                <li key={tx.id} className="flex items-center gap-3 px-3 py-2.5">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                    <RowIcon tx={tx} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1.5 truncate text-sm font-medium">
                      {title(tx)}
                      {tx.source === 'voice' && <Mic className="size-3 text-muted-foreground" aria-label="Added by voice" />}
                      {tx.source === 'text' && <Type className="size-3 text-muted-foreground" aria-label="Added by AI text" />}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {subtitle(tx)}
                      {!groupByDay && ` · ${formatDayLabel(tx.occurred_on)}`}
                    </p>
                  </div>
                  <TransactionAmount tx={tx} className="text-sm" />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8" aria-label={`Actions for ${title(tx)}`}>
                        <Ellipsis aria-hidden />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {tx.type !== 'adjustment' && (
                        <DropdownMenuItem onSelect={() => setEditing(tx)}>
                          <Pencil aria-hidden /> Edit
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(tx)}>
                        <Trash2 aria-hidden /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <TransactionFormDialog
        open={Boolean(editing)}
        onOpenChange={(open) => !open && setEditing(undefined)}
        editing={editing}
      />

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this transaction?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting && (
                <>
                  “{title(deleting)}” ({formatTaka(deleting.amount)}) will be removed and your balances
                  recalculated.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={voidTx.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void confirmDelete()
              }}
              disabled={voidTx.isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

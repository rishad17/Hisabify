import { AlertTriangle, ArrowRight, CalendarClock, CircleAlert, Loader2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { CategoryIcon } from '@/components/category-icon'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Draft, DraftIssue } from '@/features/assistant/api'
import { useCreateTransactions, useWallets, type TransactionInput } from '@/features/ledger/api'
import { WalletIcon } from '@/features/ledger/wallet-icon'
import { useCategories } from '@/features/me/api'
import { ApiError } from '@/lib/api'
import { todayISO } from '@/lib/dates'
import { formatTaka, parseAmountInput, sumAmounts } from '@/lib/money'
import { cn } from '@/lib/utils'

type EditableItem = {
  key: number
  type: 'expense' | 'income' | 'transfer'
  amount: string
  description: string
  categoryId: string
  walletId: string
  toWalletId: string
  date: string
  categoryTouched: boolean
  serverIssues: DraftIssue[]
}

const TYPE_LABEL = { expense: 'Expense', income: 'Income', transfer: 'Transfer' } as const

function clientErrors(item: EditableItem): string[] {
  const errors: string[] = []
  const amount = parseAmountInput(item.amount)
  if ('error' in amount) errors.push(amount.error)
  if (!item.walletId) errors.push('Choose a wallet.')
  if (item.type === 'transfer') {
    if (!item.toWalletId) errors.push('Choose the wallet the money went to.')
    else if (item.toWalletId === item.walletId) errors.push('From and to wallets must differ.')
  } else if (!item.categoryId) {
    errors.push('Choose a category.')
  }
  if (!item.date) errors.push('Choose a date.')
  else if (item.date > todayISO()) errors.push("Date can't be in the future.")
  return errors
}

/**
 * Editable preview of what the AI understood. NOTHING is saved until "Save" — and then
 * the backend validates everything again. The draft id is the idempotency key, so
 * double-clicking Save can never record twice.
 */
export function DraftPreview({ draft, onDone }: { draft: Draft; onDone: () => void }) {
  const wallets = useWallets()
  const categories = useCategories(true)
  const create = useCreateTransactions()
  const [serverError, setServerError] = useState<string | null>(null)
  const [items, setItems] = useState<EditableItem[]>(() =>
    draft.items.map((i, key) => ({
      key,
      type: i.type,
      amount: i.amount.replace(/\.00$/, ''),
      description: i.description,
      categoryId: i.category?.id ?? '',
      walletId: i.wallet_id ?? '',
      toWalletId: i.to_wallet_id ?? '',
      date: i.occurred_on,
      categoryTouched: false,
      // Hard errors are re-checked live on the client; keep only the warnings.
      serverIssues: i.issues.filter((issue) => issue.severity === 'warning'),
    })),
  )

  const update = (key: number, patch: Partial<EditableItem>) =>
    setItems((list) => list.map((it) => (it.key === key ? { ...it, ...patch } : it)))
  const remove = (key: number) => setItems((list) => list.filter((it) => it.key !== key))

  const errorsByKey = useMemo(
    () => new Map(items.map((it) => [it.key, clientErrors(it)])),
    [items],
  )
  const hasErrors = [...errorsByKey.values()].some((e) => e.length > 0)

  const totals = useMemo(() => {
    const valid = (type: EditableItem['type']) =>
      items
        .filter((it) => it.type === type)
        .map((it) => parseAmountInput(it.amount))
        .flatMap((p) => ('value' in p ? [p.value] : []))
    return { expense: sumAmounts(valid('expense')), income: sumAmounts(valid('income')) }
  }, [items])

  async function save() {
    setServerError(null)
    const payload: TransactionInput[] = items.map((it) => {
      const amount = parseAmountInput(it.amount)
      return {
        type: it.type,
        amount: 'value' in amount ? amount.value : it.amount,
        wallet_id: it.walletId,
        to_wallet_id: it.type === 'transfer' ? it.toWalletId : null,
        category_id: it.type === 'transfer' ? null : it.categoryId,
        description: it.description.trim() || null,
        occurred_on: it.date,
      }
    })
    try {
      const result = await create.mutateAsync({
        items: payload,
        idempotencyKey: draft.draft_id,
        source: draft.source,
      })
      const n = result.items.length
      toast.success(
        result.replayed
          ? 'Already saved — nothing duplicated.'
          : `Saved ${n} transaction${n === 1 ? '' : 's'}`,
      )
      onDone()
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Could not save. Please try again.')
    }
  }

  const walletOptions = wallets.data ?? []

  return (
    <div className="space-y-3">
      {items.length === 0 && draft.items.length > 0 && (
        <p className="text-sm text-muted-foreground">All items removed. Nothing to save.</p>
      )}

      <ul className="space-y-3">
        {items.map((it, index) => {
          const errors = errorsByKey.get(it.key) ?? []
          const warnings = it.serverIssues.filter(
            (issue) => !(issue.code === 'category_guessed' && it.categoryTouched),
          )
          const categoryOptions = (categories.data ?? []).filter((c) => c.kind === it.type)
          const category = categoryOptions.find((c) => c.id === it.categoryId)
          return (
            <li
              key={it.key}
              className={cn(
                'space-y-3 rounded-lg border bg-card p-3',
                errors.length > 0 && 'border-destructive/60',
              )}
              aria-label={`Item ${index + 1}: ${it.description}`}
            >
              <div className="flex items-center gap-2">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  {it.type === 'transfer' ? (
                    <ArrowRight className="size-4" aria-hidden />
                  ) : (
                    <CategoryIcon name={category?.icon ?? null} className="size-4" />
                  )}
                </div>
                <Badge variant={it.type === 'income' ? 'secondary' : 'outline'}>{TYPE_LABEL[it.type]}</Badge>
                <Input
                  aria-label="Description"
                  value={it.description}
                  maxLength={200}
                  onChange={(e) => update(it.key, { description: e.target.value })}
                  className="h-8 flex-1"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0"
                  onClick={() => remove(it.key)}
                  aria-label={`Remove ${it.description}`}
                >
                  <X aria-hidden />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div className="relative">
                  <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">
                    ৳
                  </span>
                  <Input
                    aria-label="Amount"
                    inputMode="decimal"
                    value={it.amount}
                    onChange={(e) => update(it.key, { amount: e.target.value })}
                    className="pl-6 font-medium tabular-nums"
                  />
                </div>

                <Select value={it.walletId} onValueChange={(v) => update(it.key, { walletId: v })}>
                  <SelectTrigger className="w-full" aria-label={it.type === 'transfer' ? 'From wallet' : 'Wallet'}>
                    <SelectValue placeholder={it.type === 'transfer' ? 'From' : 'Wallet'} />
                  </SelectTrigger>
                  <SelectContent>
                    {walletOptions.map((w) => (
                      <SelectItem key={w.id} value={w.id}>
                        <WalletIcon type={w.type} className="size-4" />
                        {w.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {it.type === 'transfer' ? (
                  <Select value={it.toWalletId} onValueChange={(v) => update(it.key, { toWalletId: v })}>
                    <SelectTrigger className="w-full" aria-label="To wallet">
                      <SelectValue placeholder="To wallet" />
                    </SelectTrigger>
                    <SelectContent>
                      {walletOptions
                        .filter((w) => w.id !== it.walletId)
                        .map((w) => (
                          <SelectItem key={w.id} value={w.id}>
                            <WalletIcon type={w.type} className="size-4" />
                            {w.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Select
                    value={it.categoryId}
                    onValueChange={(v) => update(it.key, { categoryId: v, categoryTouched: true })}
                  >
                    <SelectTrigger className="w-full" aria-label="Category">
                      <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent>
                      {categoryOptions.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          <CategoryIcon name={c.icon} className="size-4" />
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                <Input
                  type="date"
                  aria-label="Date"
                  max={todayISO()}
                  value={it.date}
                  onChange={(e) => update(it.key, { date: e.target.value })}
                />
              </div>

              {(errors.length > 0 || warnings.length > 0) && (
                <ul className="space-y-1 text-xs">
                  {errors.map((message) => (
                    <li key={message} className="flex items-start gap-1.5 text-destructive">
                      <CircleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
                      {message}
                    </li>
                  ))}
                  {warnings.map((issue) => (
                    <li key={issue.code} className="flex items-start gap-1.5 text-amber-700 dark:text-amber-400">
                      <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden />
                      {issue.message}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>

      {draft.planned.length > 0 && (
        <div className="rounded-lg border border-dashed p-3 text-sm">
          <p className="mb-1 flex items-center gap-1.5 font-medium">
            <CalendarClock className="size-4" aria-hidden /> Not recorded — future plans
          </p>
          <ul className="list-inside list-disc text-muted-foreground">
            {draft.planned.map((p, i) => (
              <li key={i}>
                {p.description}
                {p.amount && ` · ${formatTaka(p.amount)}`}
                {p.date && ` · ${p.date}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {serverError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive" role="alert">
          <CircleAlert className="size-4" aria-hidden /> {serverError}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
        <dl className="flex gap-4 text-sm">
          {totals.expense !== '0.00' && (
            <div>
              <dt className="text-xs text-muted-foreground">Spending</dt>
              <dd className="font-semibold tabular-nums">{formatTaka(totals.expense)}</dd>
            </div>
          )}
          {totals.income !== '0.00' && (
            <div>
              <dt className="text-xs text-muted-foreground">Income</dt>
              <dd className="font-semibold text-emerald-700 tabular-nums dark:text-emerald-400">
                {formatTaka(totals.income)}
              </dd>
            </div>
          )}
        </dl>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onDone} disabled={create.isPending}>
            {draft.items.length === 0 ? 'OK' : 'Discard'}
          </Button>
          <Button onClick={save} disabled={items.length === 0 || hasErrors || create.isPending}>
            {create.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Save {items.length > 1 ? `${items.length} transactions` : ''}
          </Button>
        </div>
      </div>
    </div>
  )
}

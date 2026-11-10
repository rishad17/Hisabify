import { AlertCircle, ArrowRight, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { toast } from 'sonner'

import { CategoryIcon } from '@/components/category-icon'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  useCreateTransactions,
  useUpdateTransaction,
  useWallets,
  type Transaction,
  type TransactionInput,
} from '@/features/ledger/api'
import { WalletIcon } from '@/features/ledger/wallet-icon'
import { useCategories } from '@/features/me/api'
import { ApiError } from '@/lib/api'
import { todayISO } from '@/lib/dates'
import { formatTaka, parseAmountInput } from '@/lib/money'

type FormType = TransactionInput['type']

type FormState = {
  type: FormType
  amount: string
  walletId: string
  toWalletId: string
  categoryId: string
  description: string
  date: string
}

function initialState(editing: Transaction | undefined, defaultWalletId: string): FormState {
  if (editing && editing.type !== 'adjustment') {
    return {
      type: editing.type,
      amount: editing.amount.replace(/\.00$/, ''),
      walletId: editing.wallet_id,
      toWalletId: editing.to_wallet_id ?? '',
      categoryId: editing.category?.id ?? '',
      description: editing.description ?? '',
      date: editing.occurred_on,
    }
  }
  return {
    type: 'expense',
    amount: '',
    walletId: defaultWalletId,
    toWalletId: '',
    categoryId: '',
    description: '',
    date: todayISO(),
  }
}

export function TransactionFormDialog({
  open,
  onOpenChange,
  editing,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** When set, the dialog edits this transaction instead of creating a new one. */
  editing?: Transaction
}) {
  const wallets = useWallets()
  const categories = useCategories(true)
  const create = useCreateTransactions()
  const update = useUpdateTransaction()

  const defaultWalletId = wallets.data?.find((w) => w.is_default)?.id ?? wallets.data?.[0]?.id ?? ''
  const [form, setForm] = useState<FormState>(() => initialState(editing, defaultWalletId))
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [serverError, setServerError] = useState<string | null>(null)
  // One idempotency key per opened form: double-clicking "Save" or retrying after a
  // network error can never create the transaction twice.
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())

  // Reset everything each time the dialog opens.
  useEffect(() => {
    if (open) {
      setForm(initialState(editing, defaultWalletId))
      setErrors({})
      setServerError(null)
      setIdempotencyKey(crypto.randomUUID())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing?.id])

  // Wallets may load after the dialog opened.
  useEffect(() => {
    if (!form.walletId && defaultWalletId) setForm((f) => ({ ...f, walletId: defaultWalletId }))
  }, [defaultWalletId, form.walletId])

  const categoryOptions = useMemo(
    () => (categories.data ?? []).filter((c) => c.kind === form.type),
    [categories.data, form.type],
  )
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  const changeType = (type: FormType) => {
    // Categories don't carry across expense/income, and transfers have none.
    setForm((f) => ({ ...f, type, categoryId: '', toWalletId: type === 'transfer' ? f.toWalletId : '' }))
    setErrors({})
  }

  const pending = create.isPending || update.isPending
  const isEdit = Boolean(editing)

  function validate(): TransactionInput | null {
    const next: typeof errors = {}
    const amount = parseAmountInput(form.amount)
    if ('error' in amount) next.amount = amount.error
    if (!form.walletId) next.walletId = 'Choose a wallet.'
    if (form.type === 'transfer') {
      if (!form.toWalletId) next.toWalletId = 'Choose where the money goes.'
      else if (form.toWalletId === form.walletId) next.toWalletId = 'Pick a different wallet.'
    } else if (!form.categoryId) {
      next.categoryId = 'Choose a category.'
    }
    if (!form.date) next.date = 'Choose a date.'
    else if (form.date > todayISO()) next.date = "Can't be in the future."

    setErrors(next)
    if (Object.keys(next).length > 0 || 'error' in amount) return null
    return {
      type: form.type,
      amount: amount.value,
      wallet_id: form.walletId,
      to_wallet_id: form.type === 'transfer' ? form.toWalletId : null,
      category_id: form.type === 'transfer' ? null : form.categoryId,
      description: form.description.trim() || null,
      occurred_on: form.date,
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setServerError(null)
    const input = validate()
    if (!input) return
    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, ...input })
        toast.success('Transaction updated')
      } else {
        await create.mutateAsync({ items: [input], idempotencyKey })
        const label =
          input.type === 'transfer'
            ? 'Transfer saved'
            : `${input.type === 'income' ? 'Income' : 'Expense'} saved`
        toast.success(`${label} · ${formatTaka(input.amount)}`)
      }
      onOpenChange(false)
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  const activeWallets = wallets.data ?? []

  return (
    <Dialog open={open} onOpenChange={(o) => !pending && onOpenChange(o)}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit transaction' : 'Add transaction'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Balances update automatically.' : 'Record money spent, received or moved.'}
          </DialogDescription>
        </DialogHeader>

        <form id="transaction-form" onSubmit={onSubmit} className="space-y-4" noValidate>
          {serverError && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          )}

          <Tabs value={form.type} onValueChange={(v) => changeType(v as FormType)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="expense">Expense</TabsTrigger>
              <TabsTrigger value="income">Income</TabsTrigger>
              <TabsTrigger value="transfer">Transfer</TabsTrigger>
            </TabsList>
          </Tabs>

          <Field label="Amount (৳)" htmlFor="amount" error={errors.amount}>
            <Input
              id="amount"
              inputMode="decimal"
              autoComplete="off"
              placeholder="e.g. 150 or ১৫০"
              autoFocus={!isEdit}
              value={form.amount}
              aria-invalid={Boolean(errors.amount)}
              onChange={(e) => set('amount', e.target.value)}
              className="text-lg tabular-nums"
            />
          </Field>

          <div className={form.type === 'transfer' ? 'grid grid-cols-[1fr_auto_1fr] items-start gap-2' : ''}>
            <Field
              label={form.type === 'transfer' ? 'From' : form.type === 'income' ? 'Into wallet' : 'Paid from'}
              htmlFor="wallet"
              error={errors.walletId}
            >
              <Select value={form.walletId} onValueChange={(v) => set('walletId', v)}>
                <SelectTrigger id="wallet" className="w-full" aria-invalid={Boolean(errors.walletId)}>
                  <SelectValue placeholder="Wallet" />
                </SelectTrigger>
                <SelectContent>
                  {activeWallets.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      <WalletIcon type={w.type} className="size-4" />
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            {form.type === 'transfer' && (
              <>
                <ArrowRight className="mt-8 size-4 text-muted-foreground" aria-hidden />
                <Field label="To" htmlFor="to-wallet" error={errors.toWalletId}>
                  <Select value={form.toWalletId} onValueChange={(v) => set('toWalletId', v)}>
                    <SelectTrigger id="to-wallet" className="w-full" aria-invalid={Boolean(errors.toWalletId)}>
                      <SelectValue placeholder="Wallet" />
                    </SelectTrigger>
                    <SelectContent>
                      {activeWallets
                        .filter((w) => w.id !== form.walletId)
                        .map((w) => (
                          <SelectItem key={w.id} value={w.id}>
                            <WalletIcon type={w.type} className="size-4" />
                            {w.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </Field>
              </>
            )}
          </div>
          {form.type === 'transfer' && activeWallets.length < 2 && (
            <p className="text-sm text-muted-foreground">
              Add a second wallet (e.g. bKash) on the Wallets page to make transfers.
            </p>
          )}

          {form.type !== 'transfer' && (
            <Field label="Category" htmlFor="category" error={errors.categoryId}>
              <Select value={form.categoryId} onValueChange={(v) => set('categoryId', v)}>
                <SelectTrigger id="category" className="w-full" aria-invalid={Boolean(errors.categoryId)}>
                  <SelectValue placeholder="Choose a category" />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      <CategoryIcon name={c.icon} className="size-4" />
                      {c.name}
                      {c.name_bn && <span className="text-muted-foreground">· {c.name_bn}</span>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-[10rem_1fr]">
            <Field label="Date" htmlFor="date" error={errors.date}>
              <Input
                id="date"
                type="date"
                max={todayISO()}
                value={form.date}
                aria-invalid={Boolean(errors.date)}
                onChange={(e) => set('date', e.target.value)}
              />
            </Field>
            <Field label="Note (optional)" htmlFor="description">
              <Input
                id="description"
                maxLength={200}
                placeholder={form.type === 'transfer' ? 'e.g. Cash in' : 'e.g. Lunch with friends'}
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
              />
            </Field>
          </div>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" form="transaction-form" disabled={pending}>
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            {isEdit ? 'Save changes' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

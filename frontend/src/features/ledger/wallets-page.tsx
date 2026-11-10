import { AlertCircle, Archive, Ellipsis, Loader2, Pencil, Plus, Scale, Star } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useArchiveWallet,
  useCreateWallet,
  useSetBalance,
  useUpdateWallet,
  useWallets,
  type Wallet,
  type WalletType,
} from '@/features/ledger/api'
import { Money } from '@/features/ledger/amount'
import { WALLET_TYPES, WalletIcon, walletTypeLabel } from '@/features/ledger/wallet-icon'
import { ApiError } from '@/lib/api'
import { formatTaka, parseAmountInput } from '@/lib/money'

const errorMessage = (err: unknown) =>
  err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'

export function WalletsPage() {
  const wallets = useWallets()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Wallet | undefined>()
  const [correcting, setCorrecting] = useState<Wallet | undefined>()
  const [archiving, setArchiving] = useState<Wallet | undefined>()
  const update = useUpdateWallet()
  const archive = useArchiveWallet()

  async function makeDefault(w: Wallet) {
    try {
      await update.mutateAsync({ id: w.id, is_default: true })
      toast.success(`${w.name} is now your default wallet`)
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  async function confirmArchive() {
    if (!archiving) return
    try {
      await archive.mutateAsync(archiving.id)
      toast.success(`${archiving.name} archived`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setArchiving(undefined)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Wallets</h1>
          <p className="text-sm text-muted-foreground">
            Balances are calculated from your transactions. Use “Correct balance” if they drift from reality.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus aria-hidden /> Add wallet
        </Button>
      </div>

      {wallets.isPending && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}
      {wallets.isError && <p className="text-sm text-destructive">{wallets.error.message}</p>}

      {wallets.isSuccess && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {wallets.data.map((w) => (
            <li key={w.id}>
              <Card className="py-4">
                <CardContent className="space-y-3 px-4">
                  <div className="flex items-start gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted">
                      <WalletIcon type={w.type} className="size-5 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 truncate font-medium">
                        {w.name}
                        {w.is_default && <Badge variant="secondary">Default</Badge>}
                      </p>
                      <p className="text-xs text-muted-foreground">{walletTypeLabel(w.type)}</p>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8" aria-label={`Actions for ${w.name}`}>
                          <Ellipsis aria-hidden />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setCorrecting(w)}>
                          <Scale aria-hidden /> Correct balance
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setEditing(w)}>
                          <Pencil aria-hidden /> Rename / change type
                        </DropdownMenuItem>
                        {!w.is_default && (
                          <DropdownMenuItem onSelect={() => makeDefault(w)}>
                            <Star aria-hidden /> Make default
                          </DropdownMenuItem>
                        )}
                        {!w.is_default && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem variant="destructive" onSelect={() => setArchiving(w)}>
                              <Archive aria-hidden /> Archive
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  <Money value={w.balance} className="block text-2xl font-semibold" />
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <WalletFormDialog open={creating} onOpenChange={setCreating} />
      <WalletFormDialog
        open={Boolean(editing)}
        onOpenChange={(o) => !o && setEditing(undefined)}
        editing={editing}
      />
      <SetBalanceDialog wallet={correcting} onClose={() => setCorrecting(undefined)} />

      <AlertDialog open={Boolean(archiving)} onOpenChange={(o) => !o && setArchiving(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive {archiving?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              It will be hidden from your wallet lists. Its past transactions are kept and still count
              in your reports.
              {archiving && archiving.balance !== '0.00' && (
                <> It still holds {formatTaka(archiving.balance)} — consider transferring that first.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void confirmArchive()
              }}
              disabled={archive.isPending}
            >
              Archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function WalletFormDialog({
  open,
  onOpenChange,
  editing,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  editing?: Wallet
}) {
  const create = useCreateWallet()
  const update = useUpdateWallet()
  const [name, setName] = useState('')
  const [type, setType] = useState<WalletType>('bkash')
  const [opening, setOpening] = useState('')
  const [makeDefault, setMakeDefault] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setName(editing?.name ?? '')
    setType(editing?.type ?? 'bkash')
    setOpening('')
    setMakeDefault(false)
    setError(null)
  }, [open, editing])

  const pending = create.isPending || update.isPending

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!name.trim()) return setError('Give the wallet a name.')
    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, name: name.trim(), type })
        toast.success('Wallet updated')
      } else {
        // Empty or zero → 0; anything else must be a valid positive amount.
        let openingValue = '0'
        if (!/^\s*0*(\.0*)?\s*$/.test(opening)) {
          const parsed = parseAmountInput(opening)
          if ('error' in parsed) return setError(`Current balance: ${parsed.error}`)
          openingValue = parsed.value
        }
        await create.mutateAsync({ name: name.trim(), type, opening_balance: openingValue, is_default: makeDefault })
        toast.success(`${name.trim()} added`)
      }
      onOpenChange(false)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !pending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit wallet' : 'Add wallet'}</DialogTitle>
          <DialogDescription>
            {editing ? 'Rename it or change its type.' : 'Cash, bKash, Nagad, a bank account…'}
          </DialogDescription>
        </DialogHeader>
        <form id="wallet-form" onSubmit={onSubmit} className="space-y-4" noValidate>
          {error && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="wallet-type">Type</Label>
            <Select
              value={type}
              onValueChange={(v) => {
                const nextType = v as WalletType
                // Suggest a name when the user hasn't typed one.
                const currentLabel = walletTypeLabel(type)
                if (!editing && (!name || name === currentLabel)) setName(walletTypeLabel(nextType))
                setType(nextType)
              }}
            >
              <SelectTrigger id="wallet-type" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WALLET_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    <WalletIcon type={t.value} className="size-4" />
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="wallet-name">Name</Label>
            <Input
              id="wallet-name"
              maxLength={50}
              placeholder="e.g. bKash"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          {!editing && (
            <>
              <div className="space-y-2">
                <Label htmlFor="wallet-opening">Current balance (৳)</Label>
                <Input
                  id="wallet-opening"
                  inputMode="decimal"
                  placeholder="0"
                  value={opening}
                  onChange={(e) => setOpening(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">How much is in it right now.</p>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 accent-primary"
                  checked={makeDefault}
                  onChange={(e) => setMakeDefault(e.target.checked)}
                />
                Make this my default wallet
              </label>
            </>
          )}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" form="wallet-form" disabled={pending}>
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            {editing ? 'Save' : 'Add wallet'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SetBalanceDialog({ wallet, onClose }: { wallet?: Wallet; onClose: () => void }) {
  const setBalance = useSetBalance()
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (wallet) {
      setValue(wallet.balance.replace(/\.00$/, ''))
      setError(null)
    }
  }, [wallet])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!wallet) return
    // A wallet can be overdrawn (credit card, negative bank), so allow a leading minus.
    const negative = value.trim().startsWith('-')
    const parsed = parseAmountInput(value.trim().replace(/^-/, ''))
    let balance: string
    if ('value' in parsed) balance = negative ? `-${parsed.value}` : parsed.value
    else if (/^-?\s*0*(\.0*)?$/.test(value.trim())) balance = '0.00'
    else return setError(parsed.error)

    try {
      const tx = await setBalance.mutateAsync({ id: wallet.id, balance })
      toast.success(tx ? `${wallet.name} corrected to ${formatTaka(balance)}` : 'Balance was already correct')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Dialog open={Boolean(wallet)} onOpenChange={(o) => !o && !setBalance.isPending && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Correct {wallet?.name} balance</DialogTitle>
          <DialogDescription>
            Enter what's actually in this wallet. We'll record the difference as a balance correction — it
            won't count as income or spending.
          </DialogDescription>
        </DialogHeader>
        <form id="balance-form" onSubmit={onSubmit} className="space-y-2" noValidate>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          <Label htmlFor="real-balance">Actual balance (৳)</Label>
          <Input
            id="real-balance"
            inputMode="decimal"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          {wallet && (
            <p className="text-xs text-muted-foreground">Currently shown: {formatTaka(wallet.balance)}</p>
          )}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={setBalance.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="balance-form" disabled={setBalance.isPending}>
            {setBalance.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

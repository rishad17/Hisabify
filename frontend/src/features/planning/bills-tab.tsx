import { CalendarClock, Check, Ellipsis, HandCoins, Loader2, Pencil, Plus, Receipt, Trash2, X } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { toast } from 'sonner'

import { CategoryIcon } from '@/components/category-icon'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { useWallets } from '@/features/ledger/api'
import { WalletIcon } from '@/features/ledger/wallet-icon'
import { useCategories } from '@/features/me/api'
import {
  newKey,
  useBills,
  useCancelExpected,
  useCreateExpected,
  useDeleteBill,
  useExpected,
  usePayBill,
  useReceiveExpected,
  useSaveBill,
  type Bill,
  type ExpectedIncome,
} from '@/features/planning/api'
import { ApiError } from '@/lib/api'
import { formatDayLabel, todayISO } from '@/lib/dates'
import { formatTaka, parseAmountInput, sumAmounts } from '@/lib/money'

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')

export function BillsTab() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <BillsCard />
      <ExpectedCard />
    </div>
  )
}

// ------------------------------------------------------------------ bills

function BillsCard() {
  const bills = useBills()
  const remove = useDeleteBill()
  const [editing, setEditing] = useState<Bill | 'new' | null>(null)
  const [paying, setPaying] = useState<Bill | null>(null)

  const active = bills.data?.filter((b) => b.active) ?? []
  const unpaidTotal = sumAmounts(active.filter((b) => !b.paid).map((b) => b.amount))
  const today = todayISO()

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base"><Receipt className="size-4" aria-hidden /> Monthly bills</CardTitle>
            <CardDescription>
              {active.length ? `${formatTaka(unpaidTotal, { trimZeroDecimals: true })} still to pay this month` : 'Rent, internet, tuition fees…'}
            </CardDescription>
          </div>
          <Button size="sm" onClick={() => setEditing('new')}><Plus aria-hidden /> Add bill</Button>
        </div>
      </CardHeader>
      <CardContent>
        {bills.isPending && <Skeleton className="h-24" />}
        {bills.isError && <p className="text-sm text-destructive">{bills.error.message}</p>}
        {bills.isSuccess && bills.data.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No bills yet. Adding them makes “safe to spend” much more accurate.
          </p>
        )}
        <ul className="divide-y">
          {bills.data?.map((b) => {
            const overdue = !b.paid && b.due_date < today
            return (
              <li key={b.id} className={`flex items-center gap-3 py-2.5 ${b.active ? '' : 'opacity-60'}`}>
                <CategoryIcon name={b.category.icon} className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{b.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatTaka(b.amount, { trimZeroDecimals: true })} · due {formatDayLabel(b.due_date)}
                  </p>
                </div>
                {!b.active ? (
                  <Badge variant="outline">Paused</Badge>
                ) : b.paid ? (
                  <Badge variant="secondary"><Check aria-hidden /> Paid</Badge>
                ) : (
                  <>
                    {overdue && <Badge variant="destructive">Overdue</Badge>}
                    <Button size="sm" variant="outline" onClick={() => setPaying(b)}>Mark paid</Button>
                  </>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="size-8" aria-label={`Actions for ${b.name}`}><Ellipsis aria-hidden /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setEditing(b)}><Pencil aria-hidden /> Edit</DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={async () => {
                        if (!window.confirm(`Delete "${b.name}"? Past payments stay in your history.`)) return
                        try { await remove.mutateAsync(b.id); toast.success('Bill deleted') } catch (e) { toast.error(errMsg(e)) }
                      }}
                    >
                      <Trash2 aria-hidden /> Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            )
          })}
        </ul>
      </CardContent>
      <BillDialog bill={editing} onClose={() => setEditing(null)} />
      <PayBillDialog bill={paying} onClose={() => setPaying(null)} />
    </Card>
  )
}

function BillDialog({ bill, onClose }: { bill: Bill | 'new' | null; onClose: () => void }) {
  const categories = useCategories(true)
  const saveBill = useSaveBill()
  const editing = bill && bill !== 'new' ? bill : null
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [dueDay, setDueDay] = useState('1')
  const [active, setActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!bill) return
    setName(editing?.name ?? '')
    setAmount(editing ? editing.amount.replace(/\.00$/, '') : '')
    setCategoryId(editing?.category.id ?? '')
    setDueDay(String(editing?.due_day ?? 1))
    setActive(editing?.active ?? true)
    setError(null)
  }, [bill, editing])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const parsed = parseAmountInput(amount)
    if (!name.trim()) return setError('Give the bill a name.')
    if ('error' in parsed) return setError(parsed.error)
    if (!categoryId) return setError('Choose a category.')
    try {
      await saveBill.mutateAsync({
        id: editing?.id,
        name: name.trim(),
        amount: parsed.value,
        category_id: categoryId,
        due_day: Number(dueDay),
        ...(editing ? { active } : {}),
      })
      toast.success(editing ? 'Bill updated' : 'Bill added')
      onClose()
    } catch (err) {
      setError(errMsg(err))
    }
  }

  return (
    <Dialog open={Boolean(bill)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit bill' : 'Add monthly bill'}</DialogTitle>
          <DialogDescription>A cost you pay every month, like rent or internet.</DialogDescription>
        </DialogHeader>
        <form id="bill-form" onSubmit={submit} className="space-y-3" noValidate>
          <Field label="Name" id="bill-name"><Input id="bill-name" maxLength={80} placeholder="e.g. House rent" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount (৳)" id="bill-amount"><Input id="bill-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
            <Field label="Due day" id="bill-due">
              <Select value={dueDay} onValueChange={setDueDay}>
                <SelectTrigger id="bill-due" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{Array.from({ length: 31 }, (_, i) => <SelectItem key={i} value={String(i + 1)}>{i + 1}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
          </div>
          <Field label="Category" id="bill-cat">
            <Select value={categoryId} onValueChange={setCategoryId}>
              <SelectTrigger id="bill-cat" className="w-full"><SelectValue placeholder="Choose" /></SelectTrigger>
              <SelectContent>
                {categories.data?.filter((c) => c.kind === 'expense').map((c) => (
                  <SelectItem key={c.id} value={c.id}><CategoryIcon name={c.icon} className="size-4" />{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          {editing && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-primary" checked={active} onChange={(e) => setActive(e.target.checked)} />
              Active (uncheck to pause this bill)
            </label>
          )}
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="bill-form" disabled={saveBill.isPending}>
            {saveBill.isPending && <Loader2 className="animate-spin" aria-hidden />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PayBillDialog({ bill, onClose }: { bill: Bill | null; onClose: () => void }) {
  const wallets = useWallets()
  const pay = usePayBill()
  const [walletId, setWalletId] = useState('')
  const [key, setKey] = useState(newKey)

  useEffect(() => {
    if (!bill) return
    setWalletId(bill.wallet_id ?? wallets.data?.find((w) => w.is_default)?.id ?? '')
    setKey(newKey()) // one key per dialog → a double click can't pay twice
  }, [bill, wallets.data])

  async function confirm() {
    if (!bill || !walletId) return
    try {
      await pay.mutateAsync({ id: bill.id, wallet_id: walletId, key })
      toast.success(`${bill.name} paid · ${formatTaka(bill.amount)}`)
      onClose()
    } catch (e) {
      toast.error(errMsg(e))
    }
  }

  return (
    <Dialog open={Boolean(bill)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Pay {bill?.name}</DialogTitle>
          <DialogDescription>Records a {bill && formatTaka(bill.amount)} expense for today.</DialogDescription>
        </DialogHeader>
        <Field label="Paid from" id="pay-wallet">
          <Select value={walletId} onValueChange={setWalletId}>
            <SelectTrigger id="pay-wallet" className="w-full"><SelectValue placeholder="Wallet" /></SelectTrigger>
            <SelectContent>
              {wallets.data?.map((w) => <SelectItem key={w.id} value={w.id}><WalletIcon type={w.type} className="size-4" />{w.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={confirm} disabled={!walletId || pay.isPending}>
            {pay.isPending && <Loader2 className="animate-spin" aria-hidden />} Confirm payment
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ expected income

function ExpectedCard() {
  const expected = useExpected()
  const create = useCreateExpected()
  const cancel = useCancelExpected()
  const [adding, setAdding] = useState(false)
  const [receiving, setReceiving] = useState<ExpectedIncome | null>(null)
  const [source, setSource] = useState('')
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(todayISO())
  const [error, setError] = useState<string | null>(null)

  const total = sumAmounts(expected.data?.map((e) => e.amount) ?? [])

  async function add(e: FormEvent) {
    e.preventDefault()
    const parsed = parseAmountInput(amount)
    if (!source.trim()) return setError('Where is it coming from?')
    if ('error' in parsed) return setError(parsed.error)
    try {
      await create.mutateAsync({ source: source.trim(), amount: parsed.value, expected_on: date })
      toast.success('Expected income added')
      setAdding(false)
      setSource(''); setAmount(''); setError(null)
    } catch (err) {
      setError(errMsg(err))
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base"><HandCoins className="size-4" aria-hidden /> Expected income</CardTitle>
            <CardDescription>
              Money you're waiting for — tuition fees, freelance payments, allowance. Not counted until it arrives.
              {expected.data?.length ? ` Waiting: ${formatTaka(total, { trimZeroDecimals: true })}.` : ''}
            </CardDescription>
          </div>
          {!adding && <Button size="sm" onClick={() => setAdding(true)}><Plus aria-hidden /> Add</Button>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {adding && (
          <form onSubmit={add} className="space-y-2 rounded-lg border p-3" noValidate>
            <Input aria-label="Source" placeholder="e.g. Tuition fee from Rafi" maxLength={80} value={source} onChange={(e) => setSource(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <Input aria-label="Amount" inputMode="decimal" placeholder="Amount ৳" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <Input aria-label="Expected date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={create.isPending}>{create.isPending && <Loader2 className="animate-spin" aria-hidden />} Add</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => { setAdding(false); setError(null) }}>Cancel</Button>
            </div>
          </form>
        )}
        {expected.isPending && <Skeleton className="h-20" />}
        {expected.isSuccess && expected.data.length === 0 && !adding && (
          <p className="py-6 text-center text-sm text-muted-foreground">Nothing expected right now.</p>
        )}
        <ul className="divide-y">
          {expected.data?.map((e) => (
            <li key={e.id} className="flex items-center gap-3 py-2.5">
              <CalendarClock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{e.source}</p>
                <p className="text-xs text-muted-foreground">
                  {formatTaka(e.amount, { trimZeroDecimals: true })} · expected {formatDayLabel(e.expected_on)}
                </p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setReceiving(e)}><Check aria-hidden /> Received</Button>
              <Button variant="ghost" size="icon" className="size-8" aria-label={`Cancel ${e.source}`}
                onClick={async () => { try { await cancel.mutateAsync(e.id); toast.success('Cancelled') } catch (err) { toast.error(errMsg(err)) } }}>
                <X aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
      <ReceiveDialog item={receiving} onClose={() => setReceiving(null)} />
    </Card>
  )
}

function ReceiveDialog({ item, onClose }: { item: ExpectedIncome | null; onClose: () => void }) {
  const wallets = useWallets()
  const categories = useCategories(true)
  const receive = useReceiveExpected()
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [amount, setAmount] = useState('')
  const [key, setKey] = useState(newKey)
  const [error, setError] = useState<string | null>(null)
  const incomeCats = categories.data?.filter((c) => c.kind === 'income') ?? []

  useEffect(() => {
    if (!item) return
    setWalletId(wallets.data?.find((w) => w.is_default)?.id ?? '')
    const guess = incomeCats.find((c) => item.source.toLowerCase().includes(c.name.toLowerCase())) ?? incomeCats.find((c) => c.name === 'Other Income')
    setCategoryId(guess?.id ?? '')
    setAmount(item.amount.replace(/\.00$/, ''))
    setKey(newKey())
    setError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item])

  async function confirm() {
    if (!item) return
    const parsed = parseAmountInput(amount)
    if ('error' in parsed) return setError(parsed.error)
    if (!walletId || !categoryId) return setError('Choose a wallet and category.')
    try {
      await receive.mutateAsync({ id: item.id, key, wallet_id: walletId, category_id: categoryId, amount: parsed.value })
      toast.success(`${item.source} received · ${formatTaka(parsed.value)}`)
      onClose()
    } catch (e) {
      setError(errMsg(e))
    }
  }

  return (
    <Dialog open={Boolean(item)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Received {item?.source}</DialogTitle>
          <DialogDescription>Records it as real income today.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Amount received (৳)" id="rcv-amount"><Input id="rcv-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          <Field label="Into wallet" id="rcv-wallet">
            <Select value={walletId} onValueChange={setWalletId}>
              <SelectTrigger id="rcv-wallet" className="w-full"><SelectValue placeholder="Wallet" /></SelectTrigger>
              <SelectContent>{wallets.data?.map((w) => <SelectItem key={w.id} value={w.id}><WalletIcon type={w.type} className="size-4" />{w.name}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
          <Field label="Category" id="rcv-cat">
            <Select value={categoryId} onValueChange={setCategoryId}>
              <SelectTrigger id="rcv-cat" className="w-full"><SelectValue placeholder="Category" /></SelectTrigger>
              <SelectContent>{incomeCats.map((c) => <SelectItem key={c.id} value={c.id}><CategoryIcon name={c.icon} className="size-4" />{c.name}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={confirm} disabled={receive.isPending}>{receive.isPending && <Loader2 className="animate-spin" aria-hidden />} Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, id, children }: { label: string; id: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

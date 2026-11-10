import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useOverview,
  useTransactions,
  useWallets,
  type TransactionFilters,
  type TransactionType,
} from '@/features/ledger/api'
import { Money } from '@/features/ledger/amount'
import { AddTransactionButton } from '@/features/ledger/add-transaction-button'
import { TransactionList } from '@/features/ledger/transaction-list'
import { useCategories } from '@/features/me/api'
import { currentMonth, formatMonth, shiftMonth } from '@/lib/dates'

const ALL = 'all'

export function TransactionsPage() {
  const [month, setMonth] = useState(currentMonth())
  const [type, setType] = useState<string>(ALL)
  const [walletId, setWalletId] = useState<string>(ALL)
  const [categoryId, setCategoryId] = useState<string>(ALL)

  const filters: TransactionFilters = {
    month,
    type: type === ALL ? undefined : (type as TransactionType),
    wallet_id: walletId === ALL ? undefined : walletId,
    category_id: categoryId === ALL ? undefined : categoryId,
  }
  const list = useTransactions(filters)
  const overview = useOverview(month)
  const wallets = useWallets()
  const categories = useCategories(true)

  const isCurrent = month >= currentMonth()
  const items = list.data?.pages.flatMap((p) => p.items) ?? []
  const total = list.data?.pages[0]?.total ?? 0
  const filtered = type !== ALL || walletId !== ALL || categoryId !== ALL

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Transactions</h1>
        <AddTransactionButton className="hidden sm:inline-flex" />
      </div>

      {/* Month switcher + month totals */}
      <Card className="py-3">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 px-3">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
              <ChevronLeft aria-hidden />
            </Button>
            <span className="min-w-36 text-center font-medium" aria-live="polite">
              {formatMonth(month)}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMonth(shiftMonth(month, 1))}
              disabled={isCurrent}
              aria-label="Next month"
            >
              <ChevronRight aria-hidden />
            </Button>
          </div>
          {overview.data && (
            <dl className="flex gap-5 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Income</dt>
                <dd><Money value={overview.data.income} className="font-medium" /></dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Expenses</dt>
                <dd><Money value={overview.data.expense} className="font-medium" /></dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Net</dt>
                <dd><Money value={overview.data.net} className="font-medium" /></dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Select value={type} onValueChange={(v) => { setType(v); setCategoryId(ALL) }}>
          <SelectTrigger className="w-full" aria-label="Filter by type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            <SelectItem value="expense">Expenses</SelectItem>
            <SelectItem value="income">Income</SelectItem>
            <SelectItem value="transfer">Transfers</SelectItem>
            <SelectItem value="adjustment">Balance corrections</SelectItem>
          </SelectContent>
        </Select>
        <Select value={walletId} onValueChange={setWalletId}>
          <SelectTrigger className="w-full" aria-label="Filter by wallet">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All wallets</SelectItem>
            {wallets.data?.map((w) => (
              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={categoryId} onValueChange={setCategoryId}>
          <SelectTrigger className="w-full" aria-label="Filter by category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {categories.data
              ?.filter((c) => type === ALL || c.kind === type)
              .map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>

      {/* List */}
      {list.isPending && (
        <div className="space-y-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      )}
      {list.isError && <p className="text-sm text-destructive">{list.error.message}</p>}
      {list.isSuccess && items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="font-medium">{filtered ? 'Nothing matches these filters' : `No transactions in ${formatMonth(month)}`}</p>
            {!filtered && isCurrent && <AddTransactionButton />}
          </CardContent>
        </Card>
      )}
      {items.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground">
            Showing {items.length} of {total}
          </p>
          <TransactionList items={items} />
          {list.hasNextPage && (
            <div className="flex justify-center">
              <Button variant="outline" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
                {list.isFetchingNextPage && <Loader2 className="animate-spin" aria-hidden />}
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

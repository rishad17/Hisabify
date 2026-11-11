import { ChevronLeft, ChevronRight, ListFilter, Loader2, ReceiptText, X } from 'lucide-react'
import { useState } from 'react'

import { PageHeader } from '@/components/brand'
import { EmptyState } from '@/components/empty-state'
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
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Everything you've recorded, by day. Edit or delete any entry from its ⋯ menu."
        actions={<AddTransactionButton className="hidden sm:inline-flex lg:hidden" />}
      />

      {/* Month switcher + month totals */}
      <Card className="py-3">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 px-3 sm:px-4">
          <div className="inline-flex items-center gap-0.5 rounded-lg border bg-surface-subtle p-0.5">
            <Button variant="ghost" size="icon-sm" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
              <ChevronLeft aria-hidden />
            </Button>
            <span className="min-w-32 text-center text-sm font-medium" aria-live="polite">
              {formatMonth(month)}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setMonth(shiftMonth(month, 1))}
              disabled={isCurrent}
              aria-label="Next month"
            >
              <ChevronRight aria-hidden />
            </Button>
          </div>
          {overview.data && (
            <dl className="grid w-full grid-cols-3 divide-x text-sm sm:w-auto">
              <div className="pr-4 sm:pr-6">
                <dt className="text-xs text-muted-foreground">Income</dt>
                <dd><Money value={overview.data.income} className="font-semibold text-success" /></dd>
              </div>
              <div className="px-4 sm:px-6">
                <dt className="text-xs text-muted-foreground">Expenses</dt>
                <dd><Money value={overview.data.expense} className="font-semibold" /></dd>
              </div>
              <div className="pl-4 sm:pl-6">
                <dt className="text-xs text-muted-foreground">Net</dt>
                <dd><Money value={overview.data.net} className="font-semibold" /></dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="grid grid-cols-3 items-center gap-2 sm:flex sm:flex-wrap">
        <ListFilter className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
        <Select value={type} onValueChange={(v) => { setType(v); setCategoryId(ALL) }}>
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by type">
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
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by wallet">
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
          <SelectTrigger className="w-full sm:w-52" aria-label="Filter by category">
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
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            className="col-span-3 justify-self-start"
            onClick={() => {
              setType(ALL)
              setWalletId(ALL)
              setCategoryId(ALL)
            }}
          >
            <X aria-hidden /> Clear
          </Button>
        )}
        {items.length > 0 && (
          <p className="num ml-auto hidden text-sm text-muted-foreground sm:block">
            {items.length} of {total}
          </p>
        )}
      </div>

      {/* List */}
      {list.isPending && (
        <div className="space-y-2" role="status" aria-label="Loading transactions">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-14 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
        </div>
      )}
      {list.isError && <p className="text-sm text-destructive">{list.error.message}</p>}
      {list.isSuccess && items.length === 0 && (
        <EmptyState
          icon={filtered ? <ListFilter /> : <ReceiptText />}
          title={filtered ? 'Nothing matches these filters' : `No transactions in ${formatMonth(month)}`}
          description={
            filtered
              ? 'Try a different type, wallet or category — or clear the filters.'
              : isCurrent
                ? 'Add one by hand, or type it on the dashboard like “ajke 50 taka cha”.'
                : 'Nothing was recorded this month.'
          }
          action={!filtered && isCurrent ? <AddTransactionButton /> : undefined}
        />
      )}
      {items.length > 0 && (
        <>
          <p className="num text-sm text-muted-foreground sm:hidden">
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

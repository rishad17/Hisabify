/**
 * Data hooks for wallets, transactions and the monthly overview.
 *
 * Any change to money (create/edit/void/transfer/set-balance) invalidates all three, so
 * every screen — dashboard cards, wallet balances, lists — refreshes from the backend.
 */
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

// ------------------------------------------------------------------- types

export type WalletType = 'cash' | 'bkash' | 'nagad' | 'rocket' | 'bank' | 'savings' | 'other'

export type Wallet = {
  id: string
  name: string
  type: WalletType
  opening_balance: string
  balance: string
  is_default: boolean
}

export type TransactionType = 'expense' | 'income' | 'transfer' | 'adjustment'

export type Transaction = {
  id: string
  type: TransactionType
  amount: string
  wallet_id: string
  wallet_name: string
  to_wallet_id: string | null
  to_wallet_name: string | null
  category: { id: string; name: string; name_bn: string | null; icon: string | null } | null
  description: string | null
  occurred_on: string
  source: 'manual' | 'text' | 'voice'
  voided: boolean
  created_at: string
}

export type TransactionInput = {
  type: 'expense' | 'income' | 'transfer'
  amount: string
  wallet_id: string
  to_wallet_id?: string | null
  category_id?: string | null
  description?: string | null
  occurred_on?: string
}

export type TransactionFilters = {
  month?: string
  wallet_id?: string
  category_id?: string
  type?: TransactionType
}

type TransactionPage = { items: Transaction[]; total: number; limit: number; offset: number }

export type Overview = {
  month: string
  total_balance: string
  income: string
  expense: string
  net: string
  transaction_count: number
}

// ------------------------------------------------------------------- keys

export const ledgerKeys = {
  wallets: ['wallets'] as const,
  transactions: (filters: TransactionFilters = {}) => ['transactions', filters] as const,
  overview: (month: string) => ['overview', month] as const,
}

export function invalidateMoney(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['wallets'] }),
    queryClient.invalidateQueries({ queryKey: ['transactions'] }),
    queryClient.invalidateQueries({ queryKey: ['overview'] }),
  ])
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') qs.set(k, String(v))
  const s = qs.toString()
  return s ? `?${s}` : ''
}

// ------------------------------------------------------------------- wallets

export function useWallets() {
  return useQuery({
    queryKey: ledgerKeys.wallets,
    queryFn: () => apiFetch<Wallet[]>('/api/v1/wallets'),
  })
}

export function useCreateWallet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; type: WalletType; opening_balance: string; is_default: boolean }) =>
      apiFetch<Wallet>('/api/v1/wallets', { method: 'POST', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useUpdateWallet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; type?: WalletType; is_default?: true }) =>
      apiFetch<Wallet>(`/api/v1/wallets/${id}`, { method: 'PATCH', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useArchiveWallet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/wallets/${id}/archive`, { method: 'POST' }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useSetBalance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, balance }: { id: string; balance: string }) =>
      apiFetch<Transaction | null>(`/api/v1/wallets/${id}/set-balance`, {
        method: 'POST',
        json: { balance },
      }),
    onSuccess: () => invalidateMoney(qc),
  })
}

// ------------------------------------------------------------------- transactions

const PAGE_SIZE = 30

export function useTransactions(filters: TransactionFilters) {
  return useInfiniteQuery({
    queryKey: ledgerKeys.transactions(filters),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      apiFetch<TransactionPage>(
        `/api/v1/transactions${toQuery({ ...filters, limit: PAGE_SIZE, offset: pageParam })}`,
      ),
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined,
  })
}

export function useRecentTransactions(limit = 5) {
  return useQuery({
    queryKey: ['transactions', 'recent', limit],
    queryFn: () => apiFetch<TransactionPage>(`/api/v1/transactions?limit=${limit}`),
    select: (page) => page.items,
  })
}

export function useCreateTransactions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ items, idempotencyKey }: { items: TransactionInput[]; idempotencyKey: string }) =>
      apiFetch<{ items: Transaction[]; replayed: boolean }>('/api/v1/transactions/batch', {
        method: 'POST',
        json: { source: 'manual', items },
        headers: { 'Idempotency-Key': idempotencyKey },
      }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useUpdateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<TransactionInput> & { id: string }) =>
      apiFetch<Transaction>(`/api/v1/transactions/${id}`, { method: 'PATCH', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useVoidTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Transaction>(`/api/v1/transactions/${id}/void`, { method: 'POST' }),
    onSuccess: () => invalidateMoney(qc),
  })
}

// ------------------------------------------------------------------- overview

export function useOverview(month: string) {
  return useQuery({
    queryKey: ledgerKeys.overview(month),
    queryFn: () => apiFetch<Overview>(`/api/v1/analytics/overview?month=${month}`),
  })
}

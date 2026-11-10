import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { invalidateMoney } from '@/features/ledger/api'
import { apiFetch } from '@/lib/api'

export type CategoryBrief = {
  id: string
  name: string
  name_bn: string | null
  icon: string | null
  is_essential: boolean
}

export type DraftSource = 'fixed' | 'bill' | 'estimate' | 'suggested'

export type BudgetDraft = {
  month: string
  planned_income: string
  savings_target: string
  items: { category: CategoryBrief; amount: string; source: DraftSource }[]
  allocated: string
  unallocated: string
  shortfall: string
  basis: 'history' | 'typical' | 'none'
  explanation: string[]
}

export type BudgetStatus = {
  month: string
  planned_income: string
  savings_target: string
  explanation: string | null
  items: {
    category: CategoryBrief
    amount: string
    spent: string
    remaining: string
    percent_used: number
  }[]
  total_budget: string
  total_spent: string
  unbudgeted_spent: string
}

export type AIBudgetReply = {
  kind: 'budget_draft' | 'clarification'
  message: string | null
  understood: {
    planned_income: string | null
    savings_target: string | null
    items: { category: CategoryBrief; amount: string; fixed: boolean }[]
  }
  draft: BudgetDraft | null
}

export type Bill = {
  id: string
  name: string
  amount: string
  category: CategoryBrief
  wallet_id: string | null
  due_day: number
  due_date: string
  active: boolean
  paid: boolean
  paid_transaction_id: string | null
}

export type ExpectedIncome = {
  id: string
  source: string
  amount: string
  expected_on: string
  status: 'expected' | 'received' | 'cancelled'
  received_transaction_id: string | null
}

export type SafeToSpend = {
  month: string
  days_left: number
  spendable_balance: string
  unpaid_bills: string
  unpaid_bill_count: number
  savings_to_reserve: string
  essentials_to_reserve: string
  available: string
  flexible_budget_left: string | null
  recommended: string
  per_day: string
  expected_income: string
  available_if_expected_arrives: string
  has_budget: boolean
  confidence: 'good' | 'limited'
  notes: string[]
}

const newKey = () => crypto.randomUUID().replace(/-/g, '')

// ------------------------------------------------------------------ budgets

export function useBudget(month: string) {
  return useQuery({
    queryKey: ['budget', month],
    queryFn: () => apiFetch<{ budget: BudgetStatus | null }>(`/api/v1/budgets/${month}`),
    select: (r) => r.budget,
  })
}

export function useBudgetDraft() {
  return useMutation({
    mutationFn: (body: {
      month: string
      planned_income: string
      savings_target: string
      stated: { category_id: string; amount: string; fixed: boolean }[]
    }) => apiFetch<BudgetDraft>('/api/v1/budgets/draft', { method: 'POST', json: body }),
  })
}

export function useAIBudget() {
  return useMutation({
    mutationFn: (body: { text: string; month: string }) =>
      apiFetch<AIBudgetReply>('/api/v1/ai/budget', { method: 'POST', json: body, timeoutMs: 45_000 }),
  })
}

export function useSaveBudget(month: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      planned_income: string
      savings_target: string
      items: { category_id: string; amount: string }[]
      explanation: string | null
    }) =>
      apiFetch<{ budget: BudgetStatus }>(`/api/v1/budgets/${month}`, { method: 'PUT', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useDeleteBudget(month: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<void>(`/api/v1/budgets/${month}`, { method: 'DELETE' }),
    onSuccess: () => invalidateMoney(qc),
  })
}

// ------------------------------------------------------------------ bills

export type BillInput = {
  name: string
  amount: string
  category_id: string
  due_day: number
  wallet_id?: string | null
  active?: boolean
}

export function useBills() {
  return useQuery({ queryKey: ['bills'], queryFn: () => apiFetch<Bill[]>('/api/v1/bills') })
}

export function useSaveBill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: BillInput & { id?: string }) =>
      id
        ? apiFetch<Bill>(`/api/v1/bills/${id}`, { method: 'PATCH', json: body })
        : apiFetch<Bill>('/api/v1/bills', { method: 'POST', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useDeleteBill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/bills/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function usePayBill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, wallet_id, key }: { id: string; wallet_id: string; key?: string }) =>
      apiFetch(`/api/v1/bills/${id}/pay`, {
        method: 'POST',
        json: { wallet_id },
        headers: { 'Idempotency-Key': key ?? newKey() },
      }),
    onSuccess: () => invalidateMoney(qc),
  })
}

// ------------------------------------------------------------------ expected income

export function useExpected() {
  return useQuery({
    queryKey: ['expected'],
    queryFn: () => apiFetch<ExpectedIncome[]>('/api/v1/expected-incomes'),
  })
}

export function useCreateExpected() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { source: string; amount: string; expected_on: string }) =>
      apiFetch<ExpectedIncome>('/api/v1/expected-incomes', { method: 'POST', json: body }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useReceiveExpected() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      key,
      ...body
    }: {
      id: string
      key: string
      wallet_id: string
      category_id: string
      amount?: string
    }) =>
      apiFetch<ExpectedIncome>(`/api/v1/expected-incomes/${id}/receive`, {
        method: 'POST',
        json: body,
        headers: { 'Idempotency-Key': key },
      }),
    onSuccess: () => invalidateMoney(qc),
  })
}

export function useCancelExpected() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<ExpectedIncome>(`/api/v1/expected-incomes/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => invalidateMoney(qc),
  })
}

// ------------------------------------------------------------------ safe to spend

export function useSafeToSpend() {
  return useQuery({
    queryKey: ['safe-to-spend'],
    queryFn: () => apiFetch<SafeToSpend>('/api/v1/planning/safe-to-spend'),
  })
}

export { newKey }

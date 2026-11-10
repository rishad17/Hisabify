import { useMutation } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type DraftIssue = { code: string; message: string; severity: 'warning' | 'error' }

export type DraftItem = {
  type: 'expense' | 'income' | 'transfer'
  amount: string
  description: string
  category: { id: string; name: string; name_bn: string | null; icon: string | null } | null
  wallet_id: string | null
  wallet_name: string | null
  to_wallet_id: string | null
  to_wallet_name: string | null
  occurred_on: string
  wallet_defaulted: boolean
  issues: DraftIssue[]
}

export type Draft = {
  draft_id: string
  source: 'text' | 'voice'
  items: DraftItem[]
  planned: { description: string; amount: string | null; date: string | null }[]
  expense_total: string
  income_total: string
}

export type ToolUse = { name: string; args: Record<string, unknown>; result: Record<string, unknown> }

export type AIReply = {
  kind: 'transaction_draft' | 'clarification' | 'unsupported' | 'answer'
  message: string | null
  clarifications: string[]
  draft: Draft | null
  answer: string | null
  tools_used: ToolUse[]
}

export type HistoryTurn = { role: 'user' | 'assistant'; text: string }

export function useAIMessage() {
  return useMutation({
    mutationFn: (body: { text: string; source?: 'text' | 'voice'; history?: HistoryTurn[] }) =>
      apiFetch<AIReply>('/api/v1/ai/message', { method: 'POST', json: body, timeoutMs: 45_000 }),
  })
}

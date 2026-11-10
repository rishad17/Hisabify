import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

type ChartCategory = { id: string; name: string; name_bn: string | null; icon: string | null }

export type Breakdown = {
  month: string
  total: string
  items: { category: ChartCategory | null; amount: string; share_percent: number; other_count: number }[]
}

export type Daily = {
  month: string
  days: { date: string; expense: string; income: string }[]
  total_expense: string
  average_daily_expense: string
  days_counted: number
}

export type Monthly = {
  months: { month: string; income: string; expense: string; net: string; partial: boolean }[]
}

export type Compare = {
  month: string
  partial: boolean
  current_label: string
  previous_label: string
  current_total: string
  previous_total: string
  change: string
  items: { category: ChartCategory; current: string; previous: string; change: string }[]
}

// keepPreviousData: switching months shows the old chart until the new one arrives,
// instead of flashing a skeleton.
const opts = { placeholderData: keepPreviousData } as const

export const useBreakdown = (month: string) =>
  useQuery({
    queryKey: ['overview', 'breakdown', month],
    queryFn: () => apiFetch<Breakdown>(`/api/v1/analytics/category-breakdown?month=${month}`),
    ...opts,
  })

export const useDaily = (month: string) =>
  useQuery({
    queryKey: ['overview', 'daily', month],
    queryFn: () => apiFetch<Daily>(`/api/v1/analytics/daily?month=${month}`),
    ...opts,
  })

export const useMonthly = (months = 6) =>
  useQuery({
    queryKey: ['overview', 'monthly', months],
    queryFn: () => apiFetch<Monthly>(`/api/v1/analytics/monthly?months=${months}`),
    ...opts,
  })

export const useCompare = (month: string) =>
  useQuery({
    queryKey: ['overview', 'compare', month],
    queryFn: () => apiFetch<Compare>(`/api/v1/analytics/compare?month=${month}`),
    ...opts,
  })

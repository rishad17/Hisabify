import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type Language = 'en' | 'bn'

export type Profile = {
  id: string
  display_name: string | null
  preferred_language: Language
  timezone: string
  store_ai_text: boolean
}

export type Me = {
  profile: Profile
  email: string | null
  default_wallet_name: string | null
  category_count: number
  is_new_user: boolean
}

export type ProfileUpdate = Partial<Pick<Profile, 'display_name' | 'preferred_language' | 'store_ai_text'>>

export type Category = {
  id: string
  name: string
  name_bn: string | null
  kind: 'expense' | 'income'
  is_essential: boolean
  icon: string | null
}

export const meKeys = {
  me: ['me'] as const,
  categories: ['categories'] as const,
}

/** GET /me — the first call after sign-up also creates the profile + defaults. */
export function useMe() {
  return useQuery({
    queryKey: meKeys.me,
    queryFn: () => apiFetch<Me>('/api/v1/me', { timeoutMs: 60_000 }), // allow for cold starts
  })
}

export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ProfileUpdate) => apiFetch<Me>('/api/v1/me', { method: 'PATCH', json: body }),
    onSuccess: (me) => queryClient.setQueryData(meKeys.me, me),
  })
}

/** Categories depend on the profile existing, so this waits for useMe() to succeed. */
export function useCategories(enabled: boolean) {
  return useQuery({
    queryKey: meKeys.categories,
    queryFn: () => apiFetch<Category[]>('/api/v1/categories'),
    enabled,
  })
}

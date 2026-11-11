import { useMutation } from '@tanstack/react-query'
import { Calculator, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { CategoryIcon } from '@/components/category-icon'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCategories } from '@/features/me/api'
import { SimulationResult, type Simulation } from '@/features/planning/simulation-result'
import { apiFetch } from '@/lib/api'
import { parseAmountInput } from '@/lib/money'

const ANY = 'none'

/** "Can I afford it?" — a direct, AI-free what-if check. Records nothing. */
export function AffordCheck() {
  const categories = useCategories(true)
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState(ANY)
  const [error, setError] = useState<string | null>(null)
  const simulate = useMutation({
    mutationFn: (body: { amount: string; category_id: string | null }) =>
      apiFetch<Simulation>('/api/v1/planning/simulate', { method: 'POST', json: body }),
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const parsed = parseAmountInput(amount)
    if ('error' in parsed) return setError(parsed.error)
    try {
      await simulate.mutateAsync({ amount: parsed.value, category_id: categoryId === ANY ? null : categoryId })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not check right now.')
    }
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-primary">
            <Calculator className="size-4" aria-hidden />
          </span>
          Can I afford it?
        </CardTitle>
        <CardDescription>Check a purchase against your bills, savings and budget — without recording anything.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[9rem_minmax(0,1fr)_auto]" noValidate>
          <div className="relative">
            <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted-foreground">৳</span>
            <Input aria-label="Price" inputMode="decimal" placeholder="2500" value={amount} onChange={(e) => setAmount(e.target.value)} className="num pl-7" />
          </div>
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger className="w-full" aria-label="Category (optional)">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any category</SelectItem>
              {categories.data?.filter((c) => c.kind === 'expense').map((c) => (
                <SelectItem key={c.id} value={c.id}><CategoryIcon name={c.icon} className="size-4" />{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="submit" disabled={simulate.isPending || !amount.trim()}>
            {simulate.isPending && <Loader2 className="animate-spin" aria-hidden />} Check
          </Button>
        </form>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        {simulate.data ? (
          <div className="animate-in duration-300 fade-in-0 slide-in-from-bottom-1">
            <SimulationResult sim={simulate.data} />
          </div>
        ) : (
          !error && (
            <p className="flex flex-1 items-center justify-center rounded-lg border border-dashed bg-surface-subtle px-4 py-6 text-center text-sm text-muted-foreground">
              Enter a price to see if it fits after your bills, savings and budget.
            </p>
          )
        )}
      </CardContent>
    </Card>
  )
}

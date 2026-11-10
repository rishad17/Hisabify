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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Calculator className="size-4" aria-hidden /> Can I afford it?
        </CardTitle>
        <CardDescription>Check a purchase against your bills, savings and budget — without recording anything.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="flex flex-wrap gap-2" noValidate>
          <div className="relative w-36">
            <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">৳</span>
            <Input aria-label="Price" inputMode="decimal" placeholder="2500" value={amount} onChange={(e) => setAmount(e.target.value)} className="pl-6" />
          </div>
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger className="w-48" aria-label="Category (optional)">
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
        {simulate.data && <SimulationResult sim={simulate.data} />}
      </CardContent>
    </Card>
  )
}

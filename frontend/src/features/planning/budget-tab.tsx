import { AlertCircle, ChevronLeft, ChevronRight, Info, Loader2, Pencil, Plus, Sparkles, Trash2, Wand2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { useConfirm } from '@/components/confirm-dialog'
import { CategoryIcon } from '@/components/category-icon'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Textarea } from '@/components/ui/textarea'
import { Money } from '@/features/ledger/amount'
import { AdjustmentsPanel } from '@/features/planning/adjustments-panel'
import { useCategories } from '@/features/me/api'
import {
  useAIBudget,
  useBudget,
  useBudgetDraft,
  useDeleteBudget,
  useSaveBudget,
  type AIBudgetReply,
  type BudgetDraft,
  type BudgetStatus,
  type DraftSource,
} from '@/features/planning/api'
import { ApiError } from '@/lib/api'
import { currentMonth, formatMonth, shiftMonth } from '@/lib/dates'
import { formatTaka, isNegative, parseAmountInput, sumAmounts } from '@/lib/money'
import { cn } from '@/lib/utils'

const SOURCE_LABEL: Record<DraftSource, string> = {
  fixed: 'Fixed',
  bill: 'Bill',
  estimate: 'Your estimate',
  suggested: 'Suggested',
}

type EditorState = {
  income: string
  savings: string
  rows: { key: number; categoryId: string; amount: string; source?: DraftSource }[]
  explanation: string[]
}

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
const trim = (a: string) => a.replace(/\.00$/, '')
let rowKey = 0

function fromDraft(d: BudgetDraft): EditorState {
  return {
    income: trim(d.planned_income),
    savings: trim(d.savings_target),
    rows: d.items.map((i) => ({ key: rowKey++, categoryId: i.category.id, amount: trim(i.amount), source: i.source })),
    explanation: d.explanation,
  }
}

function fromStatus(b: BudgetStatus): EditorState {
  return {
    income: trim(b.planned_income),
    savings: trim(b.savings_target),
    rows: b.items.map((i) => ({ key: rowKey++, categoryId: i.category.id, amount: trim(i.amount) })),
    explanation: b.explanation ? b.explanation.split('\n') : [],
  }
}

export function BudgetTab() {
  const [month, setMonth] = useState(currentMonth())
  const budget = useBudget(month)
  const [editor, setEditor] = useState<EditorState | null>(null)

  const header = (
    <div className="inline-flex items-center gap-0.5 rounded-lg border bg-card p-0.5 shadow-xs">
      <Button variant="ghost" size="icon-sm" onClick={() => { setMonth(shiftMonth(month, -1)); setEditor(null) }} aria-label="Previous month">
        <ChevronLeft aria-hidden />
      </Button>
      <span className="min-w-32 text-center text-sm font-medium" aria-live="polite">{formatMonth(month)}</span>
      <Button variant="ghost" size="icon-sm" onClick={() => { setMonth(shiftMonth(month, 1)); setEditor(null) }} aria-label="Next month">
        <ChevronRight aria-hidden />
      </Button>
    </div>
  )

  if (budget.isPending) return <div className="space-y-4">{header}<Skeleton className="h-64 w-full" /></div>
  if (budget.isError) return <div className="space-y-4">{header}<p className="text-sm text-destructive">{budget.error.message}</p></div>

  return (
    <div className="space-y-4">
      {header}
      {editor ? (
        <BudgetEditor month={month} initial={editor} onClose={() => setEditor(null)} />
      ) : budget.data ? (
        <>
          <BudgetProgress month={month} budget={budget.data} onEdit={() => setEditor(fromStatus(budget.data!))} />
          <AdjustmentsPanel month={month} isCurrentMonth={month === currentMonth()} />
        </>
      ) : (
        <NoBudget month={month} onDraft={(d) => setEditor(fromDraft(d))} onManual={() => setEditor({ income: '', savings: '', rows: [], explanation: [] })} />
      )}
    </div>
  )
}

// ------------------------------------------------------------------ empty state + AI planner

function NoBudget({ month, onDraft, onManual }: { month: string; onDraft: (d: BudgetDraft) => void; onManual: () => void }) {
  const ai = useAIBudget()
  const [text, setText] = useState('')
  const [reply, setReply] = useState<AIBudgetReply | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setReply(null)
    try {
      const r = await ai.mutateAsync({ text: text.trim(), month })
      setReply(r)
      if (r.kind === 'budget_draft' && r.draft) onDraft(r.draft)
    } catch {
      /* shown below */
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4 text-primary" aria-hidden /> Plan {formatMonth(month)}
        </CardTitle>
        <CardDescription>
          Describe your month in English, বাংলা or Banglish. The AI only reads your numbers — the app does the maths, and
          you can edit everything before saving.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="space-y-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            maxLength={1000}
            disabled={ai.isPending}
            aria-label="Describe your month"
            placeholder="e.g. I have 20,000 taka this month. Rent is 5,000, food around 4,000, transport 2,000, and I want to save 3,000."
          />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!text.trim() || ai.isPending}>
              {ai.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Wand2 aria-hidden />}
              Create budget
            </Button>
            <Button type="button" variant="outline" onClick={onManual}>
              Fill in manually
            </Button>
          </div>
        </form>
        {ai.isError && (
          <Alert variant="destructive">
            <AlertCircle aria-hidden />
            <AlertDescription>{errMsg(ai.error)}</AlertDescription>
          </Alert>
        )}
        {reply?.kind === 'clarification' && (
          <Alert>
            <Info aria-hidden />
            <AlertDescription>{reply.message}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

// ------------------------------------------------------------------ editor

function BudgetEditor({ month, initial, onClose }: { month: string; initial: EditorState; onClose: () => void }) {
  const categories = useCategories(true)
  const save = useSaveBudget(month)
  const draft = useBudgetDraft()
  const [state, setState] = useState(initial)
  const [error, setError] = useState<string | null>(null)

  const expenseCats = (categories.data ?? []).filter((c) => c.kind === 'expense')
  const parsed = (v: string) => {
    if (!v.trim()) return '0'
    const p = parseAmountInput(v)
    return 'value' in p ? p.value : null
  }
  const income = parsed(state.income)
  const savings = parsed(state.savings)
  const rowValues = state.rows.map((r) => parsed(r.amount))
  const allValid = income !== null && savings !== null && rowValues.every((v) => v !== null)
  const allocated = sumAmounts(rowValues.filter((v): v is string => v !== null))
  const left = allValid ? sumAmounts([income!, `-${savings}`, `-${allocated}`]) : null
  const usedIds = new Set(state.rows.map((r) => r.categoryId))

  const setRow = (key: number, patch: Partial<EditorState['rows'][number]>) =>
    setState((s) => ({ ...s, rows: s.rows.map((r) => (r.key === key ? { ...r, ...patch, source: patch.amount !== undefined ? 'estimate' : r.source } : r)) }))

  async function suggestRest() {
    setError(null)
    if (!allValid || income === '0') return setError('Enter your money for the month first.')
    try {
      const d = await draft.mutateAsync({
        month,
        planned_income: income!,
        savings_target: savings!,
        stated: state.rows
          .filter((r) => r.categoryId && parsed(r.amount) && parsed(r.amount) !== '0')
          .map((r) => ({ category_id: r.categoryId, amount: parsed(r.amount)!, fixed: r.source === 'fixed' || r.source === 'bill' })),
      })
      setState(fromDraft(d))
    } catch (e) {
      setError(errMsg(e))
    }
  }

  async function onSave() {
    setError(null)
    if (!allValid) return setError('Fix the highlighted amounts first.')
    if (state.rows.some((r) => !r.categoryId)) return setError('Choose a category for every row.')
    try {
      await save.mutateAsync({
        planned_income: income!,
        savings_target: savings!,
        items: state.rows.map((r) => ({ category_id: r.categoryId, amount: parsed(r.amount)! })),
        explanation: state.explanation.join('\n') || null,
      })
      toast.success(`Budget for ${formatMonth(month)} saved`)
      onClose()
    } catch (e) {
      setError(errMsg(e))
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Review your budget</CardTitle>
        <CardDescription>Change anything you like. Nothing is saved until you press Save.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {state.explanation.length > 0 && (
          <ul className="space-y-1 rounded-lg bg-muted/60 p-3 text-sm text-muted-foreground">
            {state.explanation.map((line) => <li key={line}>{line}</li>)}
          </ul>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="b-income">Money for the month (৳)</Label>
            <Input id="b-income" inputMode="decimal" value={state.income} aria-invalid={income === null}
              onChange={(e) => setState((s) => ({ ...s, income: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-savings">Savings target (৳)</Label>
            <Input id="b-savings" inputMode="decimal" value={state.savings} aria-invalid={savings === null}
              onChange={(e) => setState((s) => ({ ...s, savings: e.target.value }))} />
          </div>
        </div>

        <ul className="space-y-2" aria-label="Budget categories">
          {state.rows.map((row, i) => (
            <li key={row.key} className="flex items-center gap-2">
              <Select value={row.categoryId} onValueChange={(v) => setRow(row.key, { categoryId: v })}>
                <SelectTrigger className="min-w-0 flex-1" aria-label={`Category ${i + 1}`}>
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  {expenseCats.filter((c) => c.id === row.categoryId || !usedIds.has(c.id)).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      <CategoryIcon name={c.icon} className="size-4" />
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {row.source && <Badge variant="outline" className="hidden sm:inline-flex">{SOURCE_LABEL[row.source]}</Badge>}
              <div className="relative w-32 shrink-0">
                <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">৳</span>
                <Input inputMode="decimal" aria-label={`Amount ${i + 1}`} value={row.amount} aria-invalid={rowValues[i] === null}
                  onChange={(e) => setRow(row.key, { amount: e.target.value })} className="pl-6 tabular-nums" />
              </div>
              <Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label={`Remove row ${i + 1}`}
                onClick={() => setState((s) => ({ ...s, rows: s.rows.filter((r) => r.key !== row.key) }))}>
                <X aria-hidden />
              </Button>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setState((s) => ({ ...s, rows: [...s.rows, { key: rowKey++, categoryId: '', amount: '' }] }))}>
            <Plus aria-hidden /> Add category
          </Button>
          <Button variant="outline" size="sm" onClick={suggestRest} disabled={draft.isPending}>
            {draft.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Wand2 aria-hidden />}
            Suggest the rest
          </Button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-sm">
          <div>
            <span className="text-muted-foreground">Allocated </span>
            <span className="font-medium tabular-nums">{formatTaka(allocated)}</span>
            <span className="text-muted-foreground"> + savings </span>
            <span className="font-medium tabular-nums">{formatTaka(savings ?? '0')}</span>
            {left !== null && (
              <span className={cn('ml-2 font-medium', isNegative(left) ? 'text-destructive' : left === '0.00' ? 'text-success' : 'text-warning')}>
                {isNegative(left) ? `Over by ${formatTaka(left.slice(1))}` : left === '0.00' ? '✓ Every taka assigned' : `${formatTaka(left)} unassigned`}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={save.isPending}>Cancel</Button>
            <Button onClick={onSave} disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" aria-hidden />} Save budget
            </Button>
          </div>
        </div>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </CardContent>
    </Card>
  )
}

// ------------------------------------------------------------------ progress

function BudgetProgress({ month, budget, onEdit }: { month: string; budget: BudgetStatus; onEdit: () => void }) {
  const del = useDeleteBudget(month)
  const confirm = useConfirm()
  const totalPercent = budget.total_budget === '0.00' ? 0 : Math.round((Number(budget.total_spent) / Number(budget.total_budget)) * 100)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">Budget vs actual</CardTitle>
            <CardDescription>
              Spent <Money value={budget.total_spent} className="font-medium text-foreground" /> of{' '}
              <Money value={budget.total_budget} className="font-medium text-foreground" /> ({totalPercent}%) · savings target{' '}
              {formatTaka(budget.savings_target, { trimZeroDecimals: true })}
            </CardDescription>
          </div>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" onClick={onEdit}><Pencil aria-hidden /> Edit</Button>
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-destructive" aria-label="Delete budget" disabled={del.isPending}
              onClick={async () => {
                const ok = await confirm({
                  title: `Delete the budget for ${formatMonth(month)}?`,
                  description: 'Your transactions are not affected.',
                  confirmLabel: 'Delete budget',
                  destructive: true,
                })
                if (!ok) return
                try { await del.mutateAsync(); toast.success('Budget deleted') } catch (e) { toast.error(errMsg(e)) }
              }}>
              <Trash2 aria-hidden />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="grid gap-x-10 gap-y-5 md:grid-cols-2">
          {budget.items.map((item) => {
            const over = isNegative(item.remaining)
            const tone = over ? 'bg-destructive' : item.percent_used >= 80 ? 'bg-warning' : 'bg-primary'
            return (
              <li key={item.category.id} className="space-y-2">
                <div className="flex items-center gap-2.5 text-sm">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-foreground/70 dark:bg-white/[0.06]">
                    <CategoryIcon name={item.category.icon} className="size-3.5" />
                  </span>
                  <span className="flex-1 truncate font-medium">{item.category.name}</span>
                  <span className="num text-muted-foreground">
                    {formatTaka(item.spent, { trimZeroDecimals: true })} / {formatTaka(item.amount, { trimZeroDecimals: true })}
                  </span>
                </div>
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-label={`${item.category.name} budget used`}
                  aria-valuenow={Math.min(item.percent_used, 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className={cn('h-full rounded-full transition-[width] duration-500 ease-out', tone)} style={{ width: `${Math.min(item.percent_used, 100)}%` }} />
                </div>
                <p className={cn('text-xs', over ? 'text-destructive' : item.percent_used >= 80 ? 'text-warning' : 'text-muted-foreground')}>
                  {over
                    ? `Over budget by ${formatTaka(item.remaining.slice(1), { trimZeroDecimals: true })}`
                    : `${item.percent_used}% used · ${formatTaka(item.remaining, { trimZeroDecimals: true })} left`}
                </p>
              </li>
            )
          })}
        </ul>
        {budget.unbudgeted_spent !== '0.00' && (
          <p className="text-sm text-muted-foreground">
            Also spent {formatTaka(budget.unbudgeted_spent)} in categories without a budget.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

import { useSearchParams } from 'react-router'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AffordCheck } from '@/features/planning/afford-check'
import { BillsTab } from '@/features/planning/bills-tab'
import { BudgetTab } from '@/features/planning/budget-tab'
import { SafeToSpendCard } from '@/features/planning/safe-to-spend-card'

export function PlanPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'bills' ? 'bills' : 'budget'

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Plan</h1>
        <p className="text-sm text-muted-foreground">
          Your budget, monthly bills and expected income — the app reserves them before telling you what's safe to spend.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <SafeToSpendCard />
        <AffordCheck />
      </div>
      <Tabs value={tab} onValueChange={(v) => setParams(v === 'bills' ? { tab: 'bills' } : {}, { replace: true })}>
        <TabsList>
          <TabsTrigger value="budget">Budget</TabsTrigger>
          <TabsTrigger value="bills">Bills &amp; income</TabsTrigger>
        </TabsList>
        <TabsContent value="budget" className="pt-3">
          <BudgetTab />
        </TabsContent>
        <TabsContent value="bills" className="pt-3">
          <BillsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

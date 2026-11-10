import { AlertCircle, Languages, RefreshCw, Wallet } from 'lucide-react'

import { CategoryIcon } from '@/components/category-icon'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useCategories, useMe, useUpdateMe, type Category, type Language } from '@/features/me/api'

/**
 * Phase 1 home: proves the full auth round-trip (Supabase login → JWT → FastAPI →
 * Postgres) and shows the account that was set up on first login.
 * The real dashboard replaces this in Phase 3.
 */
export function HomePage() {
  const me = useMe()
  const categories = useCategories(me.isSuccess)
  const updateMe = useUpdateMe()

  if (me.isPending) return <HomeSkeleton />

  if (me.isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertTitle>Couldn't load your account</AlertTitle>
        <AlertDescription>
          <p>{me.error.message}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => me.refetch()}>
            <RefreshCw aria-hidden /> Try again
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  const { profile } = me.data
  const lang = profile.preferred_language
  const name = profile.display_name ?? me.data.email?.split('@')[0] ?? 'there'
  const expense = categories.data?.filter((c) => c.kind === 'expense') ?? []
  const income = categories.data?.filter((c) => c.kind === 'income') ?? []

  return (
    <div className="space-y-6">
      <section className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {me.data.is_new_user ? 'Welcome' : 'Welcome back'}, {name}
        </h1>
        <p className="text-muted-foreground">
          Your account is ready. Expense tracking arrives in the next phase.
        </p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardDescription>Default wallet</CardDescription>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Wallet className="size-5 text-primary" aria-hidden />
              {me.data.default_wallet_name ?? '—'}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Add bKash, Nagad and bank wallets in Phase 2.
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>AI reply language</CardDescription>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Languages className="size-5 text-primary" aria-hidden />
              {lang === 'bn' ? 'বাংলা' : 'English'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2" role="group" aria-label="AI reply language">
              {(['en', 'bn'] as Language[]).map((option) => (
                <Button
                  key={option}
                  size="sm"
                  variant={lang === option ? 'default' : 'outline'}
                  aria-pressed={lang === option}
                  disabled={updateMe.isPending}
                  onClick={() => updateMe.mutate({ preferred_language: option })}
                >
                  {option === 'en' ? 'English' : 'বাংলা'}
                </Button>
              ))}
            </div>
            {updateMe.isError && (
              <p className="mt-2 text-sm text-destructive">{updateMe.error.message}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your categories</CardTitle>
          <CardDescription>
            {me.data.category_count} default categories with Bangla names. The AI will use these
            to classify what you type or say.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {categories.isPending && <Skeleton className="h-24 w-full" />}
          {categories.isError && (
            <p className="text-sm text-destructive">{categories.error.message}</p>
          )}
          {categories.isSuccess && (
            <>
              <CategoryList title="Expenses" items={expense} />
              <CategoryList title="Income" items={income} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function CategoryList({ title, items }: { title: string; items: Category[] }) {
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((c) => (
          <li key={c.id} className="flex items-center gap-3 rounded-lg border px-3 py-2">
            <CategoryIcon name={c.icon} className="size-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{c.name}</p>
              {c.name_bn && <p className="truncate text-xs text-muted-foreground">{c.name_bn}</p>}
            </div>
            {c.is_essential && <Badge variant="secondary">Essential</Badge>}
          </li>
        ))}
      </ul>
    </div>
  )
}

function HomeSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading your account">
      <Skeleton className="h-9 w-64" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
      <Skeleton className="h-64" />
      <p className="text-sm text-muted-foreground">
        Connecting to the server… the free server may take up to a minute to wake up.
      </p>
    </div>
  )
}

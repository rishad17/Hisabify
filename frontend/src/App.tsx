import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleX, Loader2, RefreshCw, Wallet } from 'lucide-react'

import { ThemeToggle } from '@/components/theme-toggle'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiFetch } from '@/lib/api'
import { config } from '@/lib/config'

type HealthResponse = {
  status: 'ok'
  app: string
  version: string
  environment: string
}

/**
 * Phase 0 placeholder: proves frontend ⇄ backend wiring (env vars, CORS,
 * error shape, React Query). Replaced by the real app shell in Phase 1.
 */
export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
  })

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-6">
        <div className="flex items-center gap-2">
          <Wallet className="size-6 text-primary" aria-hidden />
          <span className="text-lg font-semibold">TakaWise AI</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 pb-12">
        <section className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Phase 0 — system check</h1>
          <p className="text-muted-foreground">
            Smart expense tracker &amp; AI budget planner. আজকে ৫০ টাকা চা — ajke 50 taka cha.
          </p>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Backend connection</CardTitle>
            <CardDescription className="break-all">{config.apiUrl}/health</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div role="status" aria-live="polite" className="flex items-center gap-2">
              {health.isPending && (
                <>
                  <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
                  <span>Checking…</span>
                </>
              )}
              {health.isSuccess && (
                <>
                  <CircleCheck className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <span>Connected</span>
                  <Badge variant="secondary">v{health.data.version}</Badge>
                  <Badge variant="outline">{health.data.environment}</Badge>
                </>
              )}
              {health.isError && (
                <>
                  <CircleX className="size-5 text-destructive" aria-hidden />
                  <span className="text-destructive">{health.error.message}</span>
                </>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => health.refetch()}
              disabled={health.isFetching}
            >
              <RefreshCw className={health.isFetching ? 'animate-spin' : undefined} />
              Retry
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

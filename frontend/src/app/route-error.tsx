import { AlertTriangle, Home, RotateCcw } from 'lucide-react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

import { Button } from '@/components/ui/button'

/**
 * Shown instead of a blank screen if a page crashes. After a new deploy, an open tab may
 * try to load a page file that no longer exists — reloading fixes that, so we offer it.
 */
export function RouteError() {
  const error = useRouteError()
  const chunkFailed = error instanceof Error && /dynamically imported module|Loading chunk/i.test(error.message)
  const status = isRouteErrorResponse(error) ? error.status : null

  return (
    <div className="flex min-h-[60svh] flex-col items-center justify-center gap-4 px-4 text-center" role="alert">
      <AlertTriangle className="size-8 text-amber-600 dark:text-amber-400" aria-hidden />
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">
          {chunkFailed ? 'A new version is available' : status === 404 ? 'Page not found' : 'Something went wrong'}
        </h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          {chunkFailed
            ? 'Reload to get the latest version of TakaWise.'
            : 'Your data is safe — nothing was saved halfway. Try reloading the page.'}
        </p>
      </div>
      <div className="flex gap-2">
        <Button onClick={() => window.location.reload()}>
          <RotateCcw aria-hidden /> Reload
        </Button>
        <Button asChild variant="outline">
          <Link to="/">
            <Home aria-hidden /> Dashboard
          </Link>
        </Button>
      </div>
    </div>
  )
}

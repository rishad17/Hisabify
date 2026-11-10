import { useQueryClient } from '@tanstack/react-query'
import { Download, Loader2, ShieldCheck, Trash2, UserX } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/features/auth/auth-provider'
import { useMe, useUpdateMe } from '@/features/me/api'
import { ApiError, apiDownload, apiFetch } from '@/lib/api'

type Danger = 'data' | 'account' | null

export function DataPrivacyCard() {
  const me = useMe()
  const updateMe = useUpdateMe()
  const { signOut } = useAuth()
  const qc = useQueryClient()
  const [downloading, setDownloading] = useState(false)
  const [danger, setDanger] = useState<Danger>(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function exportCsv() {
    setDownloading(true)
    try {
      await apiDownload('/api/v1/me/export.csv', 'hisabify-transactions.csv')
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Export failed.')
    } finally {
      setDownloading(false)
    }
  }

  async function confirmDanger() {
    if (typed !== 'DELETE' || !danger) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch<void>(danger === 'data' ? '/api/v1/me/data' : '/api/v1/me', {
        method: 'DELETE',
        json: { confirm: 'DELETE' },
      })
      if (danger === 'account') {
        toast.success('Your account and all data were deleted.')
        await signOut()
      } else {
        qc.clear() // every cached number is now stale
        toast.success('All your data was deleted. You have a fresh start.')
        setDanger(null)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Nothing was deleted.')
    } finally {
      setBusy(false)
    }
  }

  const storeText = me.data?.profile.store_ai_text ?? false

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="size-4" aria-hidden /> Your data &amp; privacy
        </CardTitle>
        <CardDescription>Your financial data belongs to you.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>Only you can see your data. Every request is checked against your sign-in.</li>
          <li>Voice recordings are turned into text and never stored.</li>
          <li>
            What you type to the AI is sent to Google Gemini to understand it. It isn't saved here unless you turn on
            the option below.
          </li>
          <li>The app never connects to your bank or bKash and can't move real money.</li>
        </ul>

        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-primary"
            checked={storeText}
            disabled={updateMe.isPending || me.isPending}
            onChange={(e) => updateMe.mutate({ store_ai_text: e.target.checked })}
          />
          <span>
            Save my AI messages to help debug wrong answers
            <span className="block text-xs text-muted-foreground">Off by default. Only you and the app's logs use them.</span>
          </span>
        </label>

        <Separator />

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={exportCsv} disabled={downloading}>
            {downloading ? <Loader2 className="animate-spin" aria-hidden /> : <Download aria-hidden />}
            Export transactions (CSV)
          </Button>
          <Button variant="outline" className="text-destructive" onClick={() => { setDanger('data'); setTyped(''); setError(null) }}>
            <Trash2 aria-hidden /> Delete all my data
          </Button>
          <Button variant="outline" className="text-destructive" onClick={() => { setDanger('account'); setTyped(''); setError(null) }}>
            <UserX aria-hidden /> Delete my account
          </Button>
        </div>
      </CardContent>

      <Dialog open={danger !== null} onOpenChange={(o) => !o && !busy && setDanger(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{danger === 'account' ? 'Delete your account?' : 'Delete all your data?'}</DialogTitle>
            <DialogDescription>
              {danger === 'account'
                ? 'This permanently deletes your sign-in and every transaction, wallet, budget and bill. It cannot be undone.'
                : 'This permanently deletes every transaction, wallet, budget and bill. You keep your login and start fresh. It cannot be undone.'}{' '}
              Consider exporting a CSV first.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-delete">
              Type <strong>DELETE</strong> to confirm
            </Label>
            <Input id="confirm-delete" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDanger(null)} disabled={busy}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDanger} disabled={typed !== 'DELETE' || busy}>
              {busy && <Loader2 className="animate-spin" aria-hidden />}
              {danger === 'account' ? 'Delete account' : 'Delete everything'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

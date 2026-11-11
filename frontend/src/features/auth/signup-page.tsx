import { AlertCircle, Loader2, MailCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/password-input'
import { AuthLayout } from '@/features/auth/auth-layout'
import { friendlyAuthError } from '@/features/auth/errors'
import { supabase } from '@/lib/supabase'

const MIN_PASSWORD = 8

export function SignupPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [checkEmail, setCheckEmail] = useState(false)

  const passwordTooShort = password.length > 0 && password.length < MIN_PASSWORD

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (password.length < MIN_PASSWORD) return
    setError(null)
    setSubmitting(true)
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      // Where the confirmation email link sends the user back to.
      options: { emailRedirectTo: window.location.origin },
    })
    setSubmitting(false)
    if (error) return setError(friendlyAuthError(error))
    // With email confirmation ON (Supabase default), there is no session yet.
    if (!data.session) setCheckEmail(true)
  }

  if (checkEmail) {
    return (
      <AuthLayout title="Check your email" description="One more step to activate your account.">
        <Alert>
          <MailCheck aria-hidden />
          <AlertTitle>Confirmation link sent</AlertTitle>
          <AlertDescription>
            We sent a link to <strong>{email.trim()}</strong>. Open it on this device to finish
            signing up. Check spam if you don't see it within a minute.
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="mt-4 w-full">
          <Link to="/login">Back to sign in</Link>
        </Button>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create your account"
      description="Track expenses in English, বাংলা or Banglish."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {error && (
          <Alert variant="destructive">
            <AlertCircle aria-hidden />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            inputMode="email"
            placeholder="you@example.com"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            aria-invalid={passwordTooShort}
            aria-describedby="password-hint"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p
            id="password-hint"
            className={passwordTooShort ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}
          >
            At least {MIN_PASSWORD} characters.
          </p>
        </div>
        <Button
          type="submit"
          size="lg"
          className="w-full"
          disabled={submitting || !email || password.length < MIN_PASSWORD}
        >
          {submitting && <Loader2 className="animate-spin" aria-hidden />}
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}

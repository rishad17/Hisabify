import { Database, MessagesSquare, Mic } from 'lucide-react'
import type { ReactNode } from 'react'

import { Logo, LogoMark } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'

const FEATURES = [
  { icon: Mic, text: 'No forms — just type or speak' },
  { icon: Database, text: 'Answers come from your own records' },
  { icon: MessagesSquare, text: 'Follow-up questions just work' },
]

export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="grid min-h-svh bg-background lg:grid-cols-[1.05fr_1fr]">
      {/* ---------- Brand panel (desktop) ---------- */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-hero-from to-hero-to p-10 text-white lg:flex lg:flex-col">
        <span className="pointer-events-none absolute -top-32 -left-24 size-96 rounded-full bg-white/10 blur-3xl" aria-hidden />
        <span className="pointer-events-none absolute -right-10 -bottom-24 text-[320px] leading-none font-bold text-white/[0.05] select-none" aria-hidden>
          ৳
        </span>

        <div className="relative flex items-center gap-2.5">
          <LogoMark className="ring-white/20" />
          <span className="text-lg font-semibold tracking-tight">TakaWise AI</span>
        </div>

        <div className="relative my-auto max-w-md space-y-8">
          <h2 className="text-4xl leading-tight font-semibold tracking-tight">
            Talk to your money like you talk to a friend.
          </h2>

          <ul className="space-y-3">
            {FEATURES.map((f) => (
              <li key={f.text} className="flex items-center gap-3 text-sm">
                <span className="flex size-8 items-center justify-center rounded-lg bg-white/12 ring-1 ring-white/15">
                  <f.icon className="size-4" aria-hidden />
                </span>
                {f.text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-hero-muted">Free · no bank connection needed · your data stays yours</p>
      </aside>

      {/* ---------- Form side ---------- */}
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-5 py-4 sm:px-8">
          <span className="lg:invisible">
            <Logo />
          </span>
          <ThemeToggle />
        </header>
        <main className="flex flex-1 items-start justify-center px-5 pt-6 pb-16 sm:items-center sm:px-8 sm:pt-0">
          <div className="w-full max-w-sm space-y-6">
            <div className="space-y-1.5">
              <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            {children}
            {footer && <div className="text-center text-sm text-muted-foreground">{footer}</div>}
          </div>
        </main>
      </div>
    </div>
  )
}

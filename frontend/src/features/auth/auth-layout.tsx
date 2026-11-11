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
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-hero-from to-hero-to p-12 text-white lg:flex lg:flex-col">
        {/* Faint dot grid for texture */}
        <span
          className="pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)] bg-[radial-gradient(rgb(255_255_255/0.09)_1px,transparent_1px)] [background-size:22px_22px]"
          aria-hidden
        />
        <span className="pointer-events-none absolute -top-32 -left-24 size-96 rounded-full bg-white/10 blur-3xl" aria-hidden />
        <span className="pointer-events-none absolute -right-10 -bottom-24 text-[320px] leading-none font-bold text-white/[0.05] select-none" aria-hidden>
          ৳
        </span>

        <div className="relative flex items-center gap-2.5">
          <LogoMark className="ring-white/20" />
          <span className="text-lg font-semibold tracking-tight">Hisab<span className="text-hero-muted">ify</span></span>
        </div>

        <div className="relative my-auto max-w-lg space-y-8">
          <h2 className="text-[42px] leading-[1.1] font-semibold tracking-[-0.03em] [text-wrap:wrap]">
            Talk to your money.
            <span className="block text-hero-muted">Then let it work for you.</span>
          </h2>

          <ul className="space-y-3.5">
            {FEATURES.map((f) => (
              <li key={f.text} className="flex items-center gap-3 text-[15px] text-white/90">
                <span className="flex size-9 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15 backdrop-blur-sm">
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
        <header className="flex h-16 items-center justify-between px-5 sm:px-8">
          <span className="lg:invisible">
            <Logo />
          </span>
          <ThemeToggle />
        </header>
        <main className="flex flex-1 items-start justify-center px-5 pt-6 pb-16 sm:items-center sm:px-8 sm:pt-0">
          <div className="w-full max-w-sm animate-in space-y-7 duration-300 fade-in-0 slide-in-from-bottom-2">
            <div className="space-y-1.5">
              <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.02em]">{title}</h1>
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

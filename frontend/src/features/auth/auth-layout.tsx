import type { ReactNode } from 'react'

import { Kicker, Logo } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'

const FEATURES = [
  'No forms. Just type or speak.',
  'Answers come from your own records.',
  'Follow-up questions just work.',
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
    <div className="grid min-h-svh bg-background lg:grid-cols-[1.1fr_1fr]">
      {/* ---------- Editorial brand block (desktop) ---------- */}
      <aside className="hidden flex-col justify-between bg-hero-to p-12 text-white lg:flex">
        <Logo size="lg" className="text-white [&>span]:text-hero-muted" />

        <div className="space-y-10">
          <h2 className="max-w-xl font-display text-[56px] leading-[0.98] font-extrabold tracking-[-0.035em] text-balance">
            Talk to your money.
            <span className="block text-hero-muted">Then let it work for you.</span>
          </h2>
          <ol className="max-w-md border-t border-white/25">
            {FEATURES.map((text, i) => (
              <li key={text} className="flex items-baseline gap-5 border-b border-white/25 py-3.5 text-[15px]">
                <span className="font-display text-sm font-bold text-gold tabular-nums">0{i + 1}</span>
                {text}
              </li>
            ))}
          </ol>
        </div>

        <p className="text-xs tracking-[0.14em] text-hero-muted uppercase">Free · No bank connection · Your data stays yours</p>
      </aside>

      {/* ---------- Form ---------- */}
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-6 py-5 sm:px-10">
          <span className="lg:invisible">
            <Logo />
          </span>
          <ThemeToggle />
        </header>
        <main className="flex flex-1 items-start justify-center px-6 pt-8 pb-16 sm:items-center sm:px-10 sm:pt-0">
          <div className="w-full max-w-sm space-y-7">
            <div className="space-y-2 border-t-2 border-foreground pt-4">
              <Kicker>{description}</Kicker>
              <h1 className="text-4xl leading-none font-bold">{title}</h1>
            </div>
            {children}
            {footer && <div className="text-sm text-muted-foreground">{footer}</div>}
          </div>
        </main>
      </div>
    </div>
  )
}

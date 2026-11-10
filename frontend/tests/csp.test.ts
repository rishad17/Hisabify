import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

// The CSP in vercel.json allows the inline theme script in index.html by its hash.
// If someone edits that script, this test fails instead of production silently breaking.
describe('Content-Security-Policy', () => {
  const html = readFileSync('index.html', 'utf8')
  const vercel = JSON.parse(readFileSync('vercel.json', 'utf8'))
  const csp: string = vercel.headers
    .flatMap((h: { headers: { key: string; value: string }[] }) => h.headers)
    .find((h: { key: string }) => h.key === 'Content-Security-Policy').value

  it('allows exactly the inline scripts in index.html', () => {
    const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1])
    expect(scripts.length).toBeGreaterThan(0)
    for (const body of scripts) {
      const hash = `sha256-${createHash('sha256').update(body).digest('base64')}`
      expect(csp).toContain(`'${hash}'`)
    }
  })

  it('blocks framing, plugins and unknown script sources', () => {
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).not.toContain("script-src 'self' 'unsafe-inline'")
  })
})

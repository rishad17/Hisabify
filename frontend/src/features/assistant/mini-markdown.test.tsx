import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { MiniMarkdown } from '@/features/assistant/mini-markdown'

const html = (text: string) => renderToStaticMarkup(<MiniMarkdown text={text} />)

describe('MiniMarkdown', () => {
  it('renders bold, paragraphs and bullet lists', () => {
    const out = html('You spent **৳300**.\n\n* Rent: ৳8,000\n- Food: ৳4,230')
    expect(out).toContain('<strong>৳300</strong>')
    expect(out).toContain('<li>Rent: ৳8,000</li>')
    expect(out.match(/<li>/g)).toHaveLength(2)
  })

  it('never renders model output as HTML', () => {
    const out = html('<img src=x onerror=alert(1)> **<b>hi</b>**')
    expect(out).not.toContain('<img')
    expect(out).toContain('&lt;img')
    expect(out).toContain('<strong>&lt;b&gt;hi&lt;/b&gt;</strong>')
  })
})

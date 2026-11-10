import { afterEach, describe, expect, it, vi } from 'vitest'

import { currentMonth, formatDayLabel, formatMonth, shiftMonth, todayISO } from '@/lib/dates'

afterEach(() => vi.useRealTimers())

describe('Dhaka "today"', () => {
  it('uses Bangladesh time, not UTC', () => {
    // 20:30 UTC on 10 Nov is already 02:30 on 11 Nov in Dhaka (UTC+6).
    vi.useFakeTimers({ now: new Date('2026-11-10T20:30:00Z') })
    expect(todayISO()).toBe('2026-11-11')
    expect(currentMonth()).toBe('2026-11')
  })
})

describe('shiftMonth', () => {
  it.each([
    ['2026-11', 1, '2026-12'],
    ['2026-12', 1, '2027-01'],
    ['2026-01', -1, '2025-12'],
    ['2026-03', -14, '2025-01'],
  ])('%s %+d → %s', (month, delta, expected) => {
    expect(shiftMonth(month, delta)).toBe(expected)
  })
})

describe('labels', () => {
  it('formats months', () => {
    expect(formatMonth('2026-11')).toBe('November 2026')
  })

  it('uses Today / Yesterday / dates', () => {
    vi.useFakeTimers({ now: new Date('2026-11-11T06:00:00Z') }) // 12:00 in Dhaka
    expect(formatDayLabel('2026-11-11')).toBe('Today')
    expect(formatDayLabel('2026-11-10')).toBe('Yesterday')
    expect(formatDayLabel('2026-11-03')).toBe('Tue 3 Nov')
    expect(formatDayLabel('2025-12-31')).toBe('31 Dec 2025')
  })
})

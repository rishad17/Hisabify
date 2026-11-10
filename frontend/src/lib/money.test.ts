import { describe, expect, it } from 'vitest'

import { formatTaka, isNegative, parseAmountInput, sumAmounts, toAsciiDigits } from '@/lib/money'

describe('formatTaka', () => {
  it.each([
    ['0.00', '৳0.00'],
    ['50', '৳50.00'],
    ['999.5', '৳999.50'],
    ['1000.00', '৳1,000.00'],
    ['125000.00', '৳1,25,000.00'], // lakh grouping
    ['12345678.90', '৳1,23,45,678.90'], // crore
    ['-60.00', '−৳60.00'],
    ['-0.00', '৳0.00'], // no "negative zero"
    ['0007.1', '৳7.10'],
  ])('%s → %s', (input, expected) => {
    expect(formatTaka(input)).toBe(expected)
  })

  it('shows plus for income and trims zero decimals when asked', () => {
    expect(formatTaka('500.00', { showPlus: true })).toBe('+৳500.00')
    expect(formatTaka('500.00', { trimZeroDecimals: true })).toBe('৳500')
    expect(formatTaka('500.50', { trimZeroDecimals: true })).toBe('৳500.50')
  })

  it('is exact where floats are not', () => {
    // 0.1 + 0.2 in floats is 0.30000000000000004 — the backend sends "0.30".
    expect(formatTaka('0.30')).toBe('৳0.30')
    expect(formatTaka('999999999999.99')).toBe('৳9,99,99,99,99,999.99')
  })
})

describe('parseAmountInput', () => {
  it.each([
    ['50', '50.00'],
    ['1,250.5', '1250.50'],
    ['১২০', '120.00'],
    ['৳ 300', '300.00'],
    ['007', '7.00'],
    ['12.', '12.00'],
  ])('accepts %s → %s', (input, expected) => {
    expect(parseAmountInput(input)).toEqual({ value: expected })
  })

  it.each(['', '0', '0.00', 'abc', '1.234', '-5', '1e3', '1234567890123'])('rejects %j', (input) => {
    expect(parseAmountInput(input)).toHaveProperty('error')
  })
})

describe('sumAmounts', () => {
  it('adds exactly, without float errors', () => {
    expect(sumAmounts(['100.00', '200.50', '50'])).toBe('350.50')
    expect(sumAmounts(['0.10', '0.20'])).toBe('0.30') // floats would give 0.30000000000000004
    expect(sumAmounts([])).toBe('0.00')
    expect(sumAmounts(['-60.00', '10.5'])).toBe('-49.50')
    expect(sumAmounts(['999999999999.99', '0.01'])).toBe('1000000000000.00')
  })
})

describe('helpers', () => {
  it('converts Bangla digits', () => {
    expect(toAsciiDigits('৳১,২৩৪.৫০')).toBe('৳1,234.50')
  })

  it('detects negatives but not negative zero', () => {
    expect(isNegative('-1.00')).toBe(true)
    expect(isNegative('-0.00')).toBe(false)
    expect(isNegative('5.00')).toBe(false)
  })
})

/**
 * Money helpers. The backend sends amounts as decimal STRINGS ("1250.00") and this file
 * never converts them to JavaScript numbers — floats can't represent 0.1 exactly, and
 * we never want ৳0.30000000000000004 on a screen. Totals always come from the backend.
 */

const BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯'

/** "১২৫০" → "1250" */
export function toAsciiDigits(input: string): string {
  return input.replace(/[০-৯]/g, (d) => String(BANGLA_DIGITS.indexOf(d)))
}

/** Group an integer string the South-Asian way: 1234567 → "12,34,567". */
function groupLakh(intPart: string): string {
  if (intPart.length <= 3) return intPart
  const last3 = intPart.slice(-3)
  const rest = intPart.slice(0, -3)
  return `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${last3}`
}

type FormatOptions = {
  /** Show "+" for positive values (used for income rows). */
  showPlus?: boolean
  /** Hide ".00" for whole amounts (compact lists). Default: false. */
  trimZeroDecimals?: boolean
}

/** "125000.5" → "৳1,25,000.50",  "-60.00" → "−৳60.00" */
export function formatTaka(amount: string, options: FormatOptions = {}): string {
  const raw = amount.trim()
  const negative = raw.startsWith('-')
  const unsigned = raw.replace(/^[-+]/, '')
  const [intPart = '0', decPart = ''] = unsigned.split('.')
  const decimals = (decPart + '00').slice(0, 2)
  const intClean = intPart.replace(/^0+(?=\d)/, '') || '0'

  let body = `৳${groupLakh(intClean)}`
  if (!(options.trimZeroDecimals && decimals === '00')) body += `.${decimals}`

  const isZero = /^0*$/.test(intClean + decimals)
  if (negative && !isZero) return `−${body}` // U+2212 minus sign reads better than "-"
  if (options.showPlus && !isZero) return `+${body}`
  return body
}

export function isNegative(amount: string): boolean {
  return amount.trim().startsWith('-') && !/^-0*(\.0*)?$/.test(amount.trim())
}

/**
 * Validate what the user typed in an amount box.
 * Accepts "50", "1,250.5", "১২০", "৳ 300". Returns a clean string like "1250.50",
 * or an error message.
 */
export function parseAmountInput(input: string): { value: string } | { error: string } {
  const cleaned = toAsciiDigits(input).replace(/[,৳\s]/g, '')
  if (cleaned === '') return { error: 'Enter an amount.' }
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) {
    return { error: 'Use numbers only, with at most 2 decimal places.' }
  }
  const [intPart, decPart = ''] = cleaned.split('.')
  const intClean = intPart.replace(/^0+(?=\d)/, '')
  if (intClean.length > 12) return { error: 'That amount is too large.' }
  const value = `${intClean}.${(decPart + '00').slice(0, 2)}`
  if (/^0+\.00$/.test(value)) return { error: 'Amount must be more than 0.' }
  return { value }
}

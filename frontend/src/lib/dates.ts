/**
 * Date helpers. Everything financial is in Bangladesh time (Asia/Dhaka), regardless of
 * the device's timezone — "today" must match what the backend considers today.
 */

export const APP_TIMEZONE = 'Asia/Dhaka'

/** "2026-11-11" — today's date in Dhaka. */
export function todayISO(): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', { timeZone: APP_TIMEZONE }).format(new Date())
}

/** "2026-11" — current month in Dhaka. */
export function currentMonth(): string {
  return todayISO().slice(0, 7)
}

/** shiftMonth("2026-01", -1) → "2025-12" */
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number)
  const index = y * 12 + (m - 1) + delta
  const year = Math.floor(index / 12)
  const mon = (index % 12) + 1
  return `${year}-${String(mon).padStart(2, '0')}`
}

/** "2026-11" → "November 2026" */
export function formatMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
    Date.UTC(y, m - 1, 1),
  )
}

/** Parse "YYYY-MM-DD" as a calendar date (no timezone shifting). */
function parseISODate(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

/** "Today", "Yesterday", "Mon 3 Nov", or "3 Nov 2025" for other years. */
export function formatDayLabel(iso: string): string {
  const today = todayISO()
  const days = Math.round((parseISODate(today) - parseISODate(iso)) / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  const sameYear = iso.slice(0, 4) === today.slice(0, 4)
  return new Intl.DateTimeFormat('en-GB', {
    weekday: sameYear ? 'short' : undefined,
    day: 'numeric',
    month: 'short',
    year: sameYear ? undefined : 'numeric',
    timeZone: 'UTC',
  }).format(parseISODate(iso))
}

export function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

/** Display names and address labels consistently, keeping intentional casing. */
export function formatDisplayName(value?: string | null): string {
  return (value || '').trim().split(/\s+/).map(part =>
    part === part.toLocaleLowerCase()
      ? part.replace(/(^|[^\p{L}])(\p{L})/gu, (_match, separator: string, letter: string) => separator + letter.toUpperCase())
      : part
  ).join(' ')
}

export function birthDateBounds() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = (type: string) => Number(parts.find(part => part.type === type)?.value)
  const year = value('year'), month = value('month'), day = value('day')
  const yearsAgo = (years: number) => {
    const lastDay = new Date(Date.UTC(year - years, month, 0)).getUTCDate()
    return `${year - years}-${String(month).padStart(2, '0')}-${String(Math.min(day, lastDay)).padStart(2, '0')}`
  }
  return { earliest: yearsAgo(120), latest: yearsAgo(18) }
}

export function formatCurrency(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  return `₱${num.toLocaleString('en-PH', { minimumFractionDigits: 2 })}`
}

// Soft-tinted pills with a hairline ring. Full class names are spelled out so
// Tailwind can see them at build time.
const PILL = {
  green: 'bg-green-50 text-green-800 ring-1 ring-inset ring-green-600/20',
  emerald: 'bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/25',
  blue: 'bg-blue-50 text-blue-800 ring-1 ring-inset ring-blue-600/20',
  purple: 'bg-purple-50 text-purple-800 ring-1 ring-inset ring-purple-600/20',
  // The brand palette has no orange, so this one status uses literal values.
  orange: 'bg-orange-50 text-orange-800 ring-1 ring-inset ring-orange-600/25',
  red: 'bg-red-50 text-red-800 ring-1 ring-inset ring-red-600/20',
  gray: 'bg-stone-100 text-stone-700 ring-1 ring-inset ring-stone-400/30',
}

export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    available: PILL.green,
    pending: PILL.amber,
    reserved: PILL.blue,
    adopted: PILL.emerald,
    under_medical_care: PILL.red,
    for_assessment: PILL.amber,
    inactive: PILL.gray,
    draft: PILL.gray,
    submitted: PILL.blue,
    under_review: PILL.amber,
    pending_documents: PILL.purple,
    additional_info_requested: PILL.orange,
    approved: PILL.green,
    rejected: PILL.red,
    cancelled: PILL.gray,
    adoption_completed: PILL.emerald,
    scheduled: PILL.blue,
    completed: PILL.green,
    returned: PILL.gray,
    pending_confirmation: PILL.amber,
    confirmed: PILL.green,
  }
  return map[status] || PILL.gray
}

export function capitalize(str: string): string {
  return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/**
 * Format pet age in readable text from years and months.
 *
 * Examples:
 *   formatPetAge(0, 6) -> "6 months"
 *   formatPetAge(1, 0) -> "1 year"
 *   formatPetAge(2, 3) -> "2 years and 3 months"
 *   formatPetAge(0, 0) -> "0 months"
 */
export function formatPetAge(years?: number | null, months?: number | null): string {
  if ((years === undefined || years === null) && (months === undefined || months === null)) {
    return ''
  }
  const y = Math.max(0, years ?? 0)
  const m = Math.max(0, months ?? 0)

  if (y > 0 && m > 0) {
    const yStr = y === 1 ? '1 year' : `${y} years`
    const mStr = m === 1 ? '1 month' : `${m} months`
    return `${yStr} and ${mStr}`
  }
  if (y > 0) {
    return y === 1 ? '1 year' : `${y} years`
  }
  return m === 1 ? '1 month' : `${m} months`
}

/** Shared pet-label presentation. Descriptions and stored values stay unchanged. */
export function formatPetLabel(value?: string | null): string {
  return (value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase()
    .replace(/(^|[\s/\-])(\p{L})/gu, (_match, separator: string, letter: string) => separator + letter.toLocaleUpperCase())
}

export function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
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
  orange: 'bg-[#fff1e6] text-[#9a3f0b] ring-1 ring-inset ring-[#e8590c]/25',
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
 * Pet age is stored as whole years. 0 means the pet is younger than a year,
 * which is displayed as "Under 1 year" rather than a misleading "0 years".
 */
export function formatPetAge(years?: number | null): string {
  if (years === undefined || years === null) return ''
  if (years <= 0) return 'Under 1 year'
  return years === 1 ? '1 year' : `${years} years`
}

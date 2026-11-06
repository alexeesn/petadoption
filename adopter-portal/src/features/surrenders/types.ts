export type SurrenderStatus = 'submitted' | 'needs_information' | 'waitlisted' | 'intake_scheduled' | 'declined' | 'cancelled' | 'received'

export interface SurrenderEvent {
  id: string
  action: string
  previous_status: string
  new_status: SurrenderStatus
  note: string
  intake_date: string | null
  created_at: string
  internal_notes?: string
  actor_email?: string
}

export interface SurrenderRequest {
  id: string
  pet_name: string
  species: string
  breed: string
  age_years: number
  age_months: number
  gender: string
  reason: string
  health_information: string
  behavior_information: string
  contact_number: string
  ownership_confirmed: boolean
  status: SurrenderStatus
  intake_date: string | null
  intake_instructions: string
  pet: string | null
  received_at: string | null
  created_at: string
  updated_at: string
  photos: { id: string }[]
  history: SurrenderEvent[]
  owner_email?: string
  owner_name?: string
}

export interface SurrenderPage {
  results: SurrenderRequest[]
  count: number
  next: string | null
  previous: string | null
}

export const surrenderStatuses: SurrenderStatus[] = ['submitted', 'needs_information', 'waitlisted', 'intake_scheduled', 'received', 'declined', 'cancelled']
export const statusLabel = (value: string) => value.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())
export const dateLabel = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' })
export const isClosed = (value: SurrenderStatus) => ['received', 'declined', 'cancelled'].includes(value)

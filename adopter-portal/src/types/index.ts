export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  role: 'adopter' | 'staff' | 'admin'
  is_email_verified: boolean
  date_joined: string
}

export interface LoginResponse {
  token: string
  user: User
}

export interface PetImage {
  id: string
  image: string
  caption: string
  is_primary: boolean
}

export interface Pet {
  id: string
  name: string
  species: string
  breed: string
  age_months: number
  gender: string
  size: string
  color: string
  description: string
  status: string
  is_vaccinated: boolean
  is_neutered: boolean
  adoption_fee: number
  weight_kg?: number
  images?: PetImage[]
  primary_image?: PetImage | null
  created_at?: string
}

export interface Application {
  id: string
  adopter: string
  adopter_email: string
  pet: string
  pet_name: string
  status: string
  why_adopt: string
  experience_with_pets: string
  living_situation: string
  has_other_pets: boolean
  other_pets_description: string
  references: string
  additional_notes: string
  rejection_reason?: string
  documents?: Document[]
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  application: string
  application_pet?: string
  document_type: string
  file: string
  original_filename: string
  content_type: string
  file_size: number
  notes: string
  download_url?: string
  created_at: string
}

export interface Notification {
  id: string
  title: string
  message: string
  notification_type: string
  is_read: boolean
  link: string
  created_at: string
}

export interface AdoptionRecord {
  id: string
  application_id: string
  pet: string
  pet_name: string
  adopter: string
  adopter_email: string
  status: string
  adoption_date: string
  completed_date?: string
  notes: string
  return_reason: string
  created_at: string
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: 'adopter' | 'staff' | 'admin';
  is_email_verified: boolean;
  date_joined: string;
}

export interface AdopterProfile {
  id: string;
  user_email: string;
  user_name: string;
  phone_number: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  zip_code: string;
  date_of_birth?: string;
  housing_type: string;
  owns_or_rents: string;
  has_yard: boolean;
  other_pets: string;
  household_members: number;
  created_at: string;
  updated_at: string;
}

export interface PetImage {
  id: string;
  image: string;
  caption: string;
  is_primary: boolean;
}

export interface Pet {
  id: string;
  name: string;
  species: string;
  breed: string;
  age_years: number;
  gender: string;
  size: string;
  weight_kg?: string;
  color: string;
  description: string;
  arrival_date: string | null;
  status: string;
  is_vaccinated: boolean;
  is_neutered: boolean;
  adoption_fee: string;
  images: PetImage[];
  created_at: string;
  updated_at: string;
}

export interface Application {
  id: string;
  adopter: string;
  adopter_email: string;
  adopter_name?: string;
  adopter_profile?: AdopterProfile | null;
  pet: string;
  pet_name: string;
  status: string;
  why_adopt: string;
  experience_with_pets: string;
  living_situation: string;
  has_other_pets: boolean;
  other_pets_description: string;
  references: string;
  additional_notes: string;
  staff_notes: string;
  reviewed_by?: string;
  reviewed_by_email?: string;
  reviewed_at?: string;
  rejection_reason: string;
  documents?: Document[];
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  application: string;
  document_type: string;
  file: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  notes: string;
  uploaded_by?: string;
  uploaded_by_email?: string;
  download_url?: string;
  created_at: string;
}

export interface Review {
  id: string;
  application: string;
  reviewer: string;
  reviewer_email: string;
  decision: string;
  internal_notes: string;
  adopter_visible_notes: string;
  created_at: string;
}

export interface HealthRecord {
  id: string;
  pet: string;
  pet_name: string;
  record_date: string;
  diagnosis: string;
  treatment: string;
  veterinarian_name: string;
  veterinary_clinic: string;
  next_checkup_date?: string | null;
  notes: string;
  created_by?: string;
  created_at: string;
}

export interface Vaccination {
  id: string;
  pet: string;
  vaccine_name: string;
  vaccination_date: string;
  next_due_date?: string;
  status: string;
}

export interface AdoptionPackage {
  id: string;
  name: string;
  description: string;
  price: string;
  is_active: boolean;
  created_at: string;
}

export interface AdoptionRecord {
  id: string;
  application_id: string;
  pet: string;
  pet_name: string;
  adopter: string;
  adopter_email: string;
  staff_member?: string | null;
  staff_email?: string | null;
  /** Confirmed onsite visit this record was scheduled from (null when none). */
  appointment_id?: string | null;
  appointment_date?: string | null;
  status: string;
  adoption_date: string | null;
  completed_date?: string | null;
  notes: string;
  return_reason: string;
  created_at: string;
  updated_at: string;
}

export interface Appointment {
  id: string;
  application: string;
  adopter: string;
  adopter_email: string;
  adopter_name?: string;
  pet: string;
  pet_name: string;
  requested_date: string;
  status: 'pending_confirmation' | 'confirmed' | 'rejected';
  reviewed_by?: string | null;
  reviewed_by_email?: string | null;
  reviewed_at?: string | null;
  rejection_reason: string;
  created_at: string;
  updated_at: string;
}

export interface Payment {
  id: string;
  application: string;
  application_id?: string;
  adopter_email?: string;
  adoption?: string | null;
  package?: string;
  amount: string;
  method: string;
  status: string;
  payment_date?: string | null;
  receipt_number?: string;
  reference_number?: string;
  notes?: string;
  paid_at?: string;
  processed_by?: string;
  processed_by_email?: string | null;
  package_name?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface Notification {
  id: string;
  recipient: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface AuditLog {
  id: string;
  user?: string;
  user_email?: string;
  action: string;
  model_name: string;
  object_id: string;
  previous_value: string;
  new_value: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

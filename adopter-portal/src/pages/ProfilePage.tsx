import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchAdopterProfile, updateAdopterProfile } from '../services/apiService'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'
import { formatDate } from '../utils/format'
import type { AdopterProfile } from '../types'

interface ProfileForm {
  phone_number: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  zip_code: string
  date_of_birth: string
  housing_type: string
  owns_or_rents: string
  has_yard: boolean
  household_members: number
}

const EMPTY: ProfileForm = {
  phone_number: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  zip_code: '',
  date_of_birth: '',
  housing_type: '',
  owns_or_rents: '',
  has_yard: false,
  household_members: 1,
}

/**
 * Required profile fields — mirrors the server's single source of truth
 * (AdopterProfile.REQUIRED_PROFILE_FIELDS in backend/apps/adopters/models.py),
 * which the API enforces before a new adoption application can be created.
 * Only used for inline frontend validation; the server stays authoritative.
 */
const REQUIRED_FIELDS: Array<{ name: keyof ProfileForm; label: string }> = [
  { name: 'phone_number', label: 'Phone Number' },
  { name: 'address_line1', label: 'Address Line 1' },
  { name: 'city', label: 'City' },
  { name: 'state', label: 'State / Province' },
  { name: 'zip_code', label: 'ZIP / Postal Code' },
  { name: 'housing_type', label: 'Housing Type' },
  { name: 'owns_or_rents', label: 'Own or Rent' },
]

/** Convert a saved AdopterProfile into the editable form shape. */
function profileToForm(data: AdopterProfile): ProfileForm {
  return {
    phone_number: data.phone_number ?? '',
    address_line1: data.address_line1 ?? '',
    address_line2: data.address_line2 ?? '',
    city: data.city ?? '',
    state: data.state ?? '',
    zip_code: data.zip_code ?? '',
    date_of_birth: data.date_of_birth ?? '',
    housing_type: data.housing_type ?? '',
    owns_or_rents: data.owns_or_rents ?? '',
    has_yard: data.has_yard ?? false,
    household_members: data.household_members ?? 1,
  }
}

const HOUSING_LABELS: Record<string, string> = {
  house: 'House',
  apartment: 'Apartment',
  condo: 'Condo',
  townhouse: 'Townhouse',
  other: 'Other',
}

const TENURE_LABELS: Record<string, string> = {
  own: 'Own',
  rent: 'Rent',
  other: 'Other',
}

/** A read-only label/value row used in view mode. */
function ProfileField({ label, value }: { label: string; value?: string | number | boolean | null }) {
  const display =
    value === null || value === undefined || value === ''
      ? <span className="text-stone-400 italic">Not set</span>
      : typeof value === 'boolean'
        ? value ? 'Yes' : 'No'
        : String(value)
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-1 text-sm text-stone-800">{display}</dd>
    </div>
  )
}

export default function ProfilePage() {
  const [saved, setSaved] = useState<AdopterProfile | null>(null)
  const [form, setForm] = useState<ProfileForm>(EMPTY)
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState('')
  const location = useLocation() as { state?: { from?: string } | null }
  const formRef = useRef<HTMLFormElement>(null)

  // When the adopter was sent here from the application form, offer to
  // return straight back to it after a successful save.
  const returnTo = location.state?.from

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchAdopterProfile()
      setSaved(data)
      setForm(profileToForm(data))
    } catch {
      setLoadError('Unable to load your profile.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked
        : name === 'household_members' ? Number(value) : value,
    }))
    // Clear the field's error as soon as the adopter edits it.
    setFieldErrors((prev) => {
      if (!prev[name]) return prev
      const next = { ...prev }
      delete next[name]
      return next
    })
  }

  /** Client-side mirror of the server's required-profile rule. */
  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    for (const { name, label } of REQUIRED_FIELDS) {
      const value = form[name]
      if (typeof value === 'string' && !value.trim()) {
        errors[name] = `${label} is required.`
      }
    }
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleEdit = () => {
    setError('')
    setSuccess('')
    setFieldErrors({})
    // Restore form to last saved values before enabling editing.
    if (saved) setForm(profileToForm(saved))
    setEditing(true)
    // Scroll to top of the edit area on mobile
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
  }

  const handleCancel = () => {
    setError('')
    setSuccess('')
    setFieldErrors({})
    // Discard unsaved changes and restore last saved values.
    if (saved) setForm(profileToForm(saved))
    setEditing(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!validate()) {
      setError('Please fill in the highlighted required fields before saving.')
      return
    }
    if (saving) return // prevent duplicate submissions
    setSaving(true)
    try {
      const updated = await updateAdopterProfile(form as unknown as Record<string, string | number | boolean>)
      setSaved(updated as AdopterProfile)
      setForm(profileToForm(updated as AdopterProfile))
      setEditing(false)
      setSuccess('Profile updated successfully. You can now start an adoption application.')
    } catch (err: unknown) {
      // Surface server-side field errors when available.
      const response = (err as { response?: { data?: Record<string, unknown> } })?.response
      if (response?.data && typeof response.data === 'object') {
        const data = response.data as Record<string, unknown>
        const newFieldErrors: Record<string, string> = {}
        let hasFieldError = false
        for (const [key, val] of Object.entries(data)) {
          if (Array.isArray(val)) {
            newFieldErrors[key] = (val as string[]).join(' ')
            hasFieldError = true
          } else if (typeof val === 'string') {
            newFieldErrors[key] = val
            hasFieldError = true
          }
        }
        if (hasFieldError) {
          setFieldErrors(newFieldErrors)
          setError('Please fix the errors highlighted below.')
          return
        }
      }
      setError('Failed to update profile. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />
  if (loadError) return <ErrorState message={loadError} onRetry={load} />

  const inputCls = 'field-input'

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-primary-900 mb-2">My Profile</h1>
          <p className="text-stone-500 mb-6">
            Manage your adopter profile information. Fields marked{' '}
            <span className="text-red-600" aria-hidden="true">*</span>{' '}
            <span className="sr-only">required</span>
            are required before you can start an adoption application.
          </p>
        </div>
        <Link to="/applications" className="shrink-0 text-sm font-medium text-primary-600 hover:underline">
          My Applications
        </Link>
      </div>

      {returnTo && !success && (
        <div className="mb-4">
          <Alert type="info">
            Your profile must be complete before you can fill out an adoption application. Save
            your details below, then{' '}
            <Link to={returnTo} className="font-medium underline">
              continue your application
            </Link>
            .
          </Alert>
        </div>
      )}

      {success && (
        <div className="mb-4">
          <Alert type="success">{success}</Alert>
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Alert type="error">{error}</Alert>
        </div>
      )}

      {/* ── VIEW MODE ─────────────────────────────────────────────────── */}
      {!editing && saved && (
        <div className="panel p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-primary-900">Profile Details</h2>
            <button
              type="button"
              onClick={handleEdit}
              className="btn btn-primary"
            >
              Edit Profile
            </button>
          </div>

          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
            <ProfileField label="Phone Number" value={saved.phone_number} />
            <ProfileField
              label="Date of Birth"
              value={saved.date_of_birth ? formatDate(saved.date_of_birth) : null}
            />
            <div className="sm:col-span-2">
              <ProfileField label="Address Line 1" value={saved.address_line1} />
            </div>
            <div className="sm:col-span-2">
              <ProfileField label="Address Line 2" value={saved.address_line2 || null} />
            </div>
            <ProfileField label="City" value={saved.city} />
            <ProfileField label="State / Province" value={saved.state} />
            <ProfileField label="ZIP / Postal Code" value={saved.zip_code} />
            <ProfileField
              label="Housing Type"
              value={saved.housing_type ? (HOUSING_LABELS[saved.housing_type] ?? saved.housing_type) : null}
            />
            <ProfileField
              label="Own or Rent"
              value={saved.owns_or_rents ? (TENURE_LABELS[saved.owns_or_rents] ?? saved.owns_or_rents) : null}
            />
            <ProfileField label="Household Members" value={saved.household_members} />
            <ProfileField label="Has a Yard" value={saved.has_yard} />
          </dl>
        </div>
      )}

      {/* ── EDIT MODE ─────────────────────────────────────────────────── */}
      {editing && (
        <form ref={formRef} onSubmit={handleSubmit} className="panel p-6 space-y-4" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="phone_number" className="field-label mb-1">
                Phone Number <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="phone_number" name="phone_number" type="tel" required value={form.phone_number} onChange={handleChange} aria-invalid={fieldErrors.phone_number ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.phone_number} />
            </div>
            <div>
              <label htmlFor="date_of_birth" className="field-label mb-1">Date of Birth</label>
              <input
                id="date_of_birth"
                name="date_of_birth"
                type="date"
                value={form.date_of_birth}
                onChange={handleChange}
                aria-invalid={fieldErrors.date_of_birth ? true : undefined}
                className={inputCls}
                max={new Date().toISOString().slice(0, 10)}
              />
              <FieldError message={fieldErrors.date_of_birth} />
            </div>
            <div>
              <label htmlFor="city" className="field-label mb-1">
                City <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="city" name="city" type="text" required value={form.city} onChange={handleChange} aria-invalid={fieldErrors.city ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.city} />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="address_line1" className="field-label mb-1">
                Address Line 1 <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="address_line1" name="address_line1" type="text" required value={form.address_line1} onChange={handleChange} aria-invalid={fieldErrors.address_line1 ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.address_line1} />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="address_line2" className="field-label mb-1">Address Line 2</label>
              <input id="address_line2" name="address_line2" type="text" value={form.address_line2} onChange={handleChange} className={inputCls} />
            </div>
            <div>
              <label htmlFor="state" className="field-label mb-1">
                State / Province <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="state" name="state" type="text" required value={form.state} onChange={handleChange} aria-invalid={fieldErrors.state ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.state} />
            </div>
            <div>
              <label htmlFor="zip_code" className="field-label mb-1">
                ZIP / Postal Code <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="zip_code" name="zip_code" type="text" required value={form.zip_code} onChange={handleChange} aria-invalid={fieldErrors.zip_code ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.zip_code} />
            </div>
            <div>
              <label htmlFor="housing_type" className="field-label mb-1">
                Housing Type <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <select id="housing_type" name="housing_type" required value={form.housing_type} onChange={handleChange} aria-invalid={fieldErrors.housing_type ? true : undefined} className={inputCls}>
                <option value="">Select...</option>
                <option value="house">House</option>
                <option value="apartment">Apartment</option>
                <option value="condo">Condo</option>
                <option value="townhouse">Townhouse</option>
                <option value="other">Other</option>
              </select>
              <FieldError message={fieldErrors.housing_type} />
            </div>
            <div>
              <label htmlFor="owns_or_rents" className="field-label mb-1">
                Own or Rent <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <select id="owns_or_rents" name="owns_or_rents" required value={form.owns_or_rents} onChange={handleChange} aria-invalid={fieldErrors.owns_or_rents ? true : undefined} className={inputCls}>
                <option value="">Select...</option>
                <option value="own">Own</option>
                <option value="rent">Rent</option>
                <option value="other">Other</option>
              </select>
              <FieldError message={fieldErrors.owns_or_rents} />
            </div>
            <div>
              <label htmlFor="household_members" className="field-label mb-1">Household Members</label>
              <input id="household_members" name="household_members" type="number" min="1" value={form.household_members} onChange={handleChange} className={inputCls} />
            </div>
            <div className="flex items-center">
              <label className="inline-flex items-center gap-2 text-sm text-stone-700">
                <input type="checkbox" name="has_yard" checked={form.has_yard} onChange={handleChange} className="w-4 h-4 text-primary-600" />
                I have a yard
              </label>
            </div>
          </div>

          <div className="pt-4 border-t border-stone-100 flex justify-end gap-3">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn btn-primary"
            >
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchAdopterProfile, updateAdopterProfile } from '../services/apiService'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'

interface ProfileForm {
  phone_number: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  zip_code: string
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

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileForm>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState('')
  const location = useLocation() as { state?: { from?: string } | null }

  // When the adopter was sent here from the application form, offer to
  // return straight back to it after a successful save.
  const returnTo = location.state?.from

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchAdopterProfile()
      setForm({
        phone_number: data.phone_number ?? '',
        address_line1: data.address_line1 ?? '',
        address_line2: data.address_line2 ?? '',
        city: data.city ?? '',
        state: data.state ?? '',
        zip_code: data.zip_code ?? '',
        housing_type: data.housing_type ?? '',
        owns_or_rents: data.owns_or_rents ?? '',
        has_yard: data.has_yard ?? false,
        household_members: data.household_members ?? 1,
      })
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!validate()) {
      setError('Please fill in the highlighted required fields before saving.')
      return
    }
    setSaving(true)
    try {
      await updateAdopterProfile(form as unknown as Record<string, string | number | boolean>)
      setSuccess('Profile updated successfully. You can now start an adoption application.')
    } catch {
      setError('Failed to update profile.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />
  if (loadError) return <ErrorState message={loadError} onRetry={load} />

  const inputCls =
    'w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500'

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-stone-800 mb-2">My Profile</h1>
          <p className="text-stone-500 mb-6">
            Manage your adopter profile information. Fields marked{' '}
            <span className="text-red-600" aria-hidden="true">*</span>{' '}
            <span className="sr-only">required</span>
            are required before you can start an adoption application.
          </p>
        </div>
        <Link to="/applications" className="shrink-0 text-sm font-medium text-orange-600 hover:underline">
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

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border border-orange-100 p-6 space-y-4" noValidate>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="phone_number" className="block text-sm font-medium text-stone-700 mb-1">
              Phone Number <span className="text-red-600" aria-hidden="true">*</span>
            </label>
            <input id="phone_number" name="phone_number" type="tel" required value={form.phone_number} onChange={handleChange} aria-invalid={fieldErrors.phone_number ? true : undefined} className={inputCls} />
            <FieldError message={fieldErrors.phone_number} />
          </div>
          <div>
            <label htmlFor="city" className="block text-sm font-medium text-stone-700 mb-1">
              City <span className="text-red-600" aria-hidden="true">*</span>
            </label>
            <input id="city" name="city" type="text" required value={form.city} onChange={handleChange} aria-invalid={fieldErrors.city ? true : undefined} className={inputCls} />
            <FieldError message={fieldErrors.city} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="address_line1" className="block text-sm font-medium text-stone-700 mb-1">
              Address Line 1 <span className="text-red-600" aria-hidden="true">*</span>
            </label>
            <input id="address_line1" name="address_line1" type="text" required value={form.address_line1} onChange={handleChange} aria-invalid={fieldErrors.address_line1 ? true : undefined} className={inputCls} />
            <FieldError message={fieldErrors.address_line1} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="address_line2" className="block text-sm font-medium text-stone-700 mb-1">Address Line 2</label>
            <input id="address_line2" name="address_line2" type="text" value={form.address_line2} onChange={handleChange} className={inputCls} />
          </div>
          <div>
            <label htmlFor="state" className="block text-sm font-medium text-stone-700 mb-1">
              State / Province <span className="text-red-600" aria-hidden="true">*</span>
            </label>
            <input id="state" name="state" type="text" required value={form.state} onChange={handleChange} aria-invalid={fieldErrors.state ? true : undefined} className={inputCls} />
            <FieldError message={fieldErrors.state} />
          </div>
          <div>
            <label htmlFor="zip_code" className="block text-sm font-medium text-stone-700 mb-1">
              ZIP / Postal Code <span className="text-red-600" aria-hidden="true">*</span>
            </label>
            <input id="zip_code" name="zip_code" type="text" required value={form.zip_code} onChange={handleChange} aria-invalid={fieldErrors.zip_code ? true : undefined} className={inputCls} />
            <FieldError message={fieldErrors.zip_code} />
          </div>
          <div>
            <label htmlFor="housing_type" className="block text-sm font-medium text-stone-700 mb-1">
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
            <label htmlFor="owns_or_rents" className="block text-sm font-medium text-stone-700 mb-1">
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
            <label htmlFor="household_members" className="block text-sm font-medium text-stone-700 mb-1">Household Members</label>
            <input id="household_members" name="household_members" type="number" min="1" value={form.household_members} onChange={handleChange} className={inputCls} />
          </div>
          <div className="flex items-center">
            <label className="inline-flex items-center gap-2 text-sm text-stone-700">
              <input type="checkbox" name="has_yard" checked={form.has_yard} onChange={handleChange} className="w-4 h-4 text-orange-600" />
              I have a yard
            </label>
          </div>
        </div>

        <div className="pt-4 border-t border-stone-100 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-orange-600 text-white text-sm rounded-md hover:bg-orange-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </form>
    </div>
  )
}


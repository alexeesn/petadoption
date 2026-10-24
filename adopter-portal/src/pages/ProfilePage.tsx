import { useToast } from '../context/ToastContext'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchAdopterProfile, updateAdopterProfile } from '../services/apiService'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'
import PhilippineAddressSelector, {
  type PhilippineAddress,
  EMPTY_PH_ADDRESS,
} from '../components/PhilippineAddressSelector'
import { birthDateBounds, formatDate, formatDisplayName } from '../utils/format'
import { useAuth } from '../context/AuthContext'
import type { AdopterProfile } from '../types'

interface ProfileForm {
  first_name: string
  last_name: string
  phone_number: string
  address_line1: string
  address_line2: string
  // Philippine cascading address
  region: string
  state: string   // province (blank for NCR)
  city: string    // city or municipality
  barangay: string
  zip_code: string
  date_of_birth: string
  housing_type: string
  owns_or_rents: string
  has_yard: boolean
  household_members: number
  has_children: boolean
  number_of_children: string
  children_ages: string
  has_other_pets: boolean
  other_pets: string
}

const EMPTY: ProfileForm = {
  first_name: '',
  last_name: '',
  phone_number: '',
  address_line1: '',
  address_line2: '',
  region: '',
  state: '',
  city: '',
  barangay: '',
  zip_code: '',
  date_of_birth: '',
  housing_type: '',
  owns_or_rents: '',
  has_yard: false,
  household_members: 1,
  has_children: false,
  number_of_children: '',
  children_ages: '',
  has_other_pets: false,
  other_pets: '',
}

/**
 * Required profile fields — mirrors the server's single source of truth
 * (AdopterProfile.REQUIRED_PROFILE_FIELDS in backend/apps/adopters/models.py),
 * which the API enforces before a new adoption application can be created.
 * Only used for inline frontend validation; the server stays authoritative.
 */
const REQUIRED_FIELDS: Array<{ name: keyof ProfileForm; label: string }> = [
  { name: 'first_name', label: 'First Name' },
  { name: 'last_name', label: 'Last Name' },
  { name: 'date_of_birth', label: 'Date of Birth' },
  { name: 'phone_number', label: 'Phone Number' },
  { name: 'address_line1', label: 'Street Address' },
  { name: 'region', label: 'Region' },
  { name: 'city', label: 'City / Municipality' },
  { name: 'barangay', label: 'Barangay' },
  { name: 'zip_code', label: 'ZIP / Postal Code' },
  { name: 'housing_type', label: 'Housing Type' },
  { name: 'owns_or_rents', label: 'Own or Rent' },
]

/** Convert a saved AdopterProfile into the editable form shape. */
function profileToForm(data: AdopterProfile): ProfileForm {
  return {
    first_name: formatDisplayName(data.first_name),
    last_name: formatDisplayName(data.last_name),
    phone_number: data.phone_number ?? '',
    address_line1: data.address_line1 ?? '',
    address_line2: data.address_line2 ?? '',
    region: data.region ?? '',
    state: data.state ?? '',
    city: data.city ?? '',
    barangay: data.barangay ?? '',
    zip_code: data.zip_code ?? '',
    date_of_birth: data.date_of_birth ?? '',
    housing_type: data.housing_type ?? '',
    owns_or_rents: data.owns_or_rents ?? '',
    has_yard: data.has_yard ?? false,
    household_members: data.household_members ?? 1,
    has_children: data.has_children ?? false,
    number_of_children: data.number_of_children != null ? String(data.number_of_children) : '',
    children_ages: data.children_ages ?? '',
    has_other_pets: data.has_other_pets ?? false,
    other_pets: data.other_pets ?? '',
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

/**
 * Format a saved Philippine address into a human-readable multi-line string
 * for the view mode panel.
 */
function formatPhAddress(profile: AdopterProfile): string {
  const parts: string[] = []
  if (profile.address_line1) parts.push(profile.address_line1)
  if (profile.address_line2) parts.push(profile.address_line2)
  if (profile.barangay) parts.push(profile.barangay)
  const cityLine = [profile.city, profile.state].filter(Boolean).join(', ')
  if (cityLine) parts.push(cityLine)
  if (profile.zip_code) parts.push(profile.zip_code)
  if (profile.region) parts.push(profile.region)
  return parts.map(formatDisplayName).join('\n')
}

/** Parse comma-separated ages string into an array of child age strings of length `count`. */
function parseAges(agesStr?: string | null, count?: number | null): string[] {
  const n = count && count > 0 ? count : 0
  const list = (agesStr ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
  const res: string[] = []
  for (let i = 0; i < n; i++) {
    res.push(list[i] ?? '')
  }
  return res
}

export default function ProfilePage() {
  const toast = useToast()
  const { syncProfileName } = useAuth()
  const birthdayBounds = birthDateBounds()
  const [saved, setSaved] = useState<AdopterProfile | null>(null)
  const [form, setForm] = useState<ProfileForm>(EMPTY)
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState('')
  const [childAges, setChildAges] = useState<string[]>([])
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
      setChildAges(parseAges(data.children_ages, data.number_of_children))
    } catch {
      setLoadError('Unable to load your profile.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
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

  /** Handle Yes/No toggle for children in household. */
  const handleChildrenToggle = (hasChildren: boolean) => {
    setForm((prev) => ({
      ...prev,
      has_children: hasChildren,
      number_of_children: hasChildren ? (prev.number_of_children || '1') : '',
      children_ages: '',
    }))
    if (!hasChildren) {
      setChildAges([])
    } else {
      const count = parseInt(form.number_of_children, 10) || 1
      setChildAges((prev) => {
        if (prev.length > 0) return prev
        return parseAges(form.children_ages, count)
      })
    }
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.number_of_children
      delete next.children_ages
      Object.keys(next).forEach((k) => {
        if (k.startsWith('child_age_')) delete next[k]
      })
      return next
    })
  }

  /** When the child count changes, adjust age fields while preserving remaining entries. */
  const handleChildCountChange = (value: string) => {
    setForm((prev) => ({ ...prev, number_of_children: value }))
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.number_of_children
      delete next.children_ages
      return next
    })
    const count = parseInt(value, 10)
    if (isNaN(count) || count <= 0) {
      setChildAges([])
      return
    }
    const safeCount = Math.min(count, 50)
    setChildAges((prev) => {
      if (prev.length > safeCount) {
        return prev.slice(0, safeCount)
      }
      const next = [...prev]
      while (next.length < safeCount) {
        next.push('')
      }
      return next
    })
  }

  /** Update an individual child's age value. */
  const handleChildAgeChange = (index: number, val: string) => {
    setChildAges((prev) => {
      const next = [...prev]
      next[index] = val
      return next
    })
    setFieldErrors((prev) => {
      const key = `child_age_${index}`
      if (!prev[key] && !prev.children_ages) return prev
      const next = { ...prev }
      delete next[key]
      delete next.children_ages
      return next
    })
  }

  /** Handle cascading Philippine address selector changes. */
  const handleAddressChange = (updated: PhilippineAddress) => {
    setForm((prev) => ({
      ...prev,
      region: updated.region,
      state: updated.state,
      city: updated.city,
      barangay: updated.barangay,
    }))
    // Clear address-related field errors on any address change.
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.region
      delete next.state
      delete next.city
      delete next.barangay
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
    if (form.date_of_birth && form.date_of_birth > birthdayBounds.latest) {
      errors.date_of_birth = 'You must be at least 18 years old.'
    } else if (form.date_of_birth && form.date_of_birth < birthdayBounds.earliest) {
      errors.date_of_birth = 'Date of birth must be within the last 120 years.'
    }
    if (form.has_children) {
      const count = parseInt(form.number_of_children, 10)
      if (!form.number_of_children || isNaN(count) || count < 1) {
        errors.number_of_children = 'Please enter a valid number of children (at least 1).'
      } else if (count > 50) {
        errors.number_of_children = 'Number of children must be 50 or fewer.'
      } else {
        for (let i = 0; i < count; i++) {
          const ageStr = (childAges[i] ?? '').trim()
          const key = `child_age_${i}`
          if (ageStr === '') {
            errors[key] = `Child ${i + 1} age is required.`
          } else {
            const ageNum = Number(ageStr)
            if (!Number.isInteger(ageNum) || ageNum < 0 || ageNum > 17) {
              errors[key] = `Child ${i + 1} age must be a whole number between 0 and 17.`
            }
          }
        }
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
    if (saved) {
      setForm(profileToForm(saved))
      setChildAges(parseAges(saved.children_ages, saved.number_of_children))
    }
    setEditing(true)
    // Scroll to top of the edit area on mobile
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
  }

  const handleCancel = () => {
    setError('')
    setSuccess('')
    setFieldErrors({})
    // Discard unsaved changes and restore last saved values.
    if (saved) {
      setForm(profileToForm(saved))
      setChildAges(parseAges(saved.children_ages, saved.number_of_children))
    }
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
      // Build the API payload, converting number_of_children to int/null
      // and joining individual child ages into comma-separated string.
      const childCount = form.has_children && form.number_of_children !== ''
        ? Number(form.number_of_children)
        : null
      const agesStr = form.has_children && childCount && childCount > 0
        ? childAges.slice(0, childCount).map((a) => a.trim()).join(', ')
        : ''
      const payload: Record<string, string | number | boolean | null> = {
        ...form,
        first_name: formatDisplayName(form.first_name),
        last_name: formatDisplayName(form.last_name),
        number_of_children: childCount,
        children_ages: agesStr,
        other_pets: form.has_other_pets ? form.other_pets : '',
      }
      const updated = await updateAdopterProfile(payload as Record<string, string | number | boolean | null>)
      const savedData = updated as AdopterProfile
      syncProfileName(savedData.first_name, savedData.last_name)
      setSaved(savedData)
      setForm(profileToForm(savedData))
      setChildAges(parseAges(savedData.children_ages, savedData.number_of_children))
      setEditing(false)
      setSuccess('Profile updated successfully. You can now start an adoption application.')
      toast.success('Profile saved', 'Your updated information has been saved.')
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

  // Extract PhilippineAddress shape from current form for the selector
  const phAddress: PhilippineAddress = {
    region: form.region,
    state: form.state,
    city: form.city,
    barangay: form.barangay,
  }

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
            <ProfileField label="First Name" value={formatDisplayName(saved.first_name)} />
            <ProfileField label="Last Name" value={formatDisplayName(saved.last_name)} />
            <ProfileField label="Phone Number" value={saved.phone_number} />
            <ProfileField
              label="Date of Birth"
              value={saved.date_of_birth ? formatDate(saved.date_of_birth) : null}
            />
            <div className="sm:col-span-2">
              <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">Address</dt>
              <dd className="mt-1 text-sm text-stone-800 whitespace-pre-line">
                {formatPhAddress(saved) || <span className="text-stone-400 italic">Not set</span>}
              </dd>
            </div>
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
            <ProfileField
              label="Children in Household"
              value={saved.has_children ? 'Yes' : 'No'}
            />
            {saved.has_children && (
              <>
                <ProfileField label="Number of Children" value={saved.number_of_children ?? undefined} />
                <ProfileField label="Children's Ages (years)" value={saved.children_ages || undefined} />
              </>
            )}
            <ProfileField
              label="Other Pets in Home"
              value={saved.has_other_pets ? 'Yes' : 'No'}
            />
            {saved.has_other_pets && saved.other_pets && (
              <div className="sm:col-span-2">
                <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">Current Pets Description</dt>
                <dd className="mt-1 text-sm text-stone-800 whitespace-pre-line">{saved.other_pets}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* ── EDIT MODE ─────────────────────────────────────────────────── */}
      {editing && (
        <form ref={formRef} onSubmit={handleSubmit} className="panel p-6 space-y-6" noValidate>

          {/* ── Contact ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {(['first_name', 'last_name'] as const).map(name => (
              <div key={name}>
                <label htmlFor={name} className="field-label mb-1">{name === 'first_name' ? 'First Name' : 'Last Name'} <span className="text-red-600" aria-hidden="true">*</span></label>
                <input id={name} name={name} type="text" required maxLength={150} autoCapitalize="words" autoComplete={name === 'first_name' ? 'given-name' : 'family-name'} value={form[name]} onChange={handleChange} onBlur={() => setForm(current => ({ ...current, [name]: formatDisplayName(current[name]) }))} aria-invalid={fieldErrors[name] ? true : undefined} aria-describedby={`${name}-error`} className={inputCls} />
                <div id={`${name}-error`}><FieldError message={fieldErrors[name]} /></div>
              </div>
            ))}
            <div>
              <label htmlFor="phone_number" className="field-label mb-1">
                Phone Number <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input id="phone_number" name="phone_number" type="tel" required value={form.phone_number} onChange={handleChange} aria-invalid={fieldErrors.phone_number ? true : undefined} className={inputCls} />
              <FieldError message={fieldErrors.phone_number} />
            </div>
            <div>
              <label htmlFor="date_of_birth" className="field-label mb-1">Date of Birth <span className="text-red-600" aria-hidden="true">*</span></label>
              <input
                id="date_of_birth"
                name="date_of_birth"
                type="date"
                required
                value={form.date_of_birth}
                onChange={handleChange}
                aria-invalid={fieldErrors.date_of_birth ? true : undefined}
                className={inputCls}
                min={birthdayBounds.earliest}
                max={birthdayBounds.latest}
                aria-describedby="birthday-help birthday-error"
              />
              <p id="birthday-help" className="mt-1 text-xs text-stone-500">You must be at least 18 years old to adopt.</p>
              <div id="birthday-error"><FieldError message={fieldErrors.date_of_birth} /></div>
            </div>
          </div>

          {/* ── Street Address ── */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-stone-700 border-b border-stone-100 pb-1">
              Philippine Address
            </h3>
            <div>
              <label htmlFor="address_line1" className="field-label mb-1">
                House / Unit No., Street, Purok{' '}
                <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input
                id="address_line1"
                name="address_line1"
                type="text"
                required
                value={form.address_line1}
                onChange={handleChange}
                aria-invalid={fieldErrors.address_line1 ? true : undefined}
                className={inputCls}
                placeholder="e.g. 123 Rizal Street"
              />
              <FieldError message={fieldErrors.address_line1} />
            </div>
            <div>
              <label htmlFor="address_line2" className="field-label mb-1">Address Line 2 (optional)</label>
              <input
                id="address_line2"
                name="address_line2"
                type="text"
                value={form.address_line2}
                onChange={handleChange}
                className={inputCls}
                placeholder="Subdivision, Phase, Block, Lot, etc."
              />
            </div>

            {/* Cascading Philippine address dropdowns */}
            <PhilippineAddressSelector
              value={phAddress}
              onChange={handleAddressChange}
              disabled={saving}
              errors={{
                region: fieldErrors.region,
                state: fieldErrors.state,
                city: fieldErrors.city,
                barangay: fieldErrors.barangay,
              }}
            />

            <div>
              <label htmlFor="zip_code" className="field-label mb-1">
                ZIP / Postal Code <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <input
                id="zip_code"
                name="zip_code"
                type="text"
                required
                value={form.zip_code}
                onChange={handleChange}
                aria-invalid={fieldErrors.zip_code ? true : undefined}
                className={inputCls}
                placeholder="e.g. 1000"
                maxLength={10}
              />
              <FieldError message={fieldErrors.zip_code} />
            </div>
          </div>

          {/* ── Housing ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

          {/* ── Household & Pets ── */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-stone-700 border-b border-stone-100 pb-1">
              Household &amp; Pets
            </h3>

            {/* Children Yes/No Selection */}
            <div>
              <label className="field-label mb-1">
                Children in the household <span className="text-red-600" aria-hidden="true">*</span>
              </label>
              <div className="flex items-center gap-6 mt-1" role="radiogroup" aria-label="Children in the household">
                <label className="inline-flex items-center gap-2 text-sm text-stone-700 cursor-pointer">
                  <input
                    type="radio"
                    name="has_children"
                    checked={form.has_children === true}
                    onChange={() => handleChildrenToggle(true)}
                    className="w-4 h-4 text-primary-600 focus:ring-primary-500"
                  />
                  Yes
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-stone-700 cursor-pointer">
                  <input
                    type="radio"
                    name="has_children"
                    checked={form.has_children === false}
                    onChange={() => handleChildrenToggle(false)}
                    className="w-4 h-4 text-primary-600 focus:ring-primary-500"
                  />
                  No
                </label>
              </div>
            </div>

            {form.has_children && (
              <div className="space-y-4 pl-4 border-l-2 border-primary-200">
                <div className="max-w-xs">
                  <label htmlFor="number_of_children" className="field-label mb-1">
                    Number of children <span className="text-red-600" aria-hidden="true">*</span>
                  </label>
                  <input
                    id="number_of_children"
                    name="number_of_children"
                    type="number"
                    min="1"
                    max="50"
                    value={form.number_of_children}
                    onChange={(e) => handleChildCountChange(e.target.value)}
                    aria-invalid={fieldErrors.number_of_children ? true : undefined}
                    className={inputCls}
                    placeholder="e.g. 2"
                  />
                  <FieldError message={fieldErrors.number_of_children} />
                </div>

                {fieldErrors.children_ages && (
                  <FieldError message={fieldErrors.children_ages} />
                )}

                {/* Dynamically rendered numeric fields based on selected number of children */}
                {childAges.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-stone-600 mb-2">
                      Enter the age for each child (0 to 17 years):
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                      {childAges.map((age, index) => {
                        const fieldName = `child_age_${index}`
                        return (
                          <div key={fieldName}>
                            <label htmlFor={fieldName} className="field-label mb-1">
                              Child {index + 1} age (years) <span className="text-red-600" aria-hidden="true">*</span>
                            </label>
                            <input
                              id={fieldName}
                              name={fieldName}
                              type="number"
                              min="0"
                              max="17"
                              value={age}
                              onChange={(e) => handleChildAgeChange(index, e.target.value)}
                              aria-invalid={fieldErrors[fieldName] ? true : undefined}
                              className={inputCls}
                              placeholder="e.g. 5"
                            />
                            <FieldError message={fieldErrors[fieldName]} />
                          </div>
                        )
                      })}
                    </div>
                    <p className="mt-1 text-xs text-stone-500">Ages only — no names or birthdates.</p>
                  </div>
                )}
              </div>
            )}

            {/* Other pets */}
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center gap-2 text-sm text-stone-700">
                <input
                  type="checkbox"
                  name="has_other_pets"
                  checked={form.has_other_pets}
                  onChange={handleChange}
                  className="w-4 h-4 text-primary-600"
                />
                I currently have other pets
              </label>
            </div>
            {form.has_other_pets && (
              <div className="pl-6">
                <label htmlFor="other_pets" className="field-label mb-1">
                  Describe your current pets <span className="text-red-600" aria-hidden="true">*</span>
                </label>
                <textarea
                  id="other_pets"
                  name="other_pets"
                  rows={3}
                  value={form.other_pets}
                  onChange={handleChange}
                  aria-invalid={fieldErrors.other_pets ? true : undefined}
                  className={inputCls}
                  placeholder="Types, counts, e.g. 2 dogs (Labrador, Shih Tzu), 1 cat"
                />
                <FieldError message={fieldErrors.other_pets} />
              </div>
            )}
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

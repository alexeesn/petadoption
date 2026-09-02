import { useCallback, useEffect, useState } from 'react'
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

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileForm>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
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
      setError('Unable to load your profile.')
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
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await updateAdopterProfile(form as unknown as Record<string, string | number | boolean>)
      setSuccess('Profile updated successfully.')
    } catch {
      setError('Failed to update profile.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />
  if (error) return <ErrorState message={error} onRetry={load} />

  const inputCls =
    'w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500'

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-stone-800 mb-2">My Profile</h1>
      <p className="text-stone-500 mb-6">Manage your adopter profile information.</p>

      {success && <div className="mb-4"><Alert type="success">{success}</Alert></div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border border-orange-100 p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="phone_number" className="block text-sm font-medium text-stone-700 mb-1">Phone Number</label>
            <input id="phone_number" name="phone_number" type="tel" value={form.phone_number} onChange={handleChange} className={inputCls} />
          </div>
          <div>
            <label htmlFor="city" className="block text-sm font-medium text-stone-700 mb-1">City</label>
            <input id="city" name="city" type="text" value={form.city} onChange={handleChange} className={inputCls} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="address_line1" className="block text-sm font-medium text-stone-700 mb-1">Address Line 1</label>
            <input id="address_line1" name="address_line1" type="text" value={form.address_line1} onChange={handleChange} className={inputCls} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="address_line2" className="block text-sm font-medium text-stone-700 mb-1">Address Line 2</label>
            <input id="address_line2" name="address_line2" type="text" value={form.address_line2} onChange={handleChange} className={inputCls} />
          </div>
          <div>
            <label htmlFor="state" className="block text-sm font-medium text-stone-700 mb-1">State / Province</label>
            <input id="state" name="state" type="text" value={form.state} onChange={handleChange} className={inputCls} />
          </div>
          <div>
            <label htmlFor="zip_code" className="block text-sm font-medium text-stone-700 mb-1">ZIP / Postal Code</label>
            <input id="zip_code" name="zip_code" type="text" value={form.zip_code} onChange={handleChange} className={inputCls} />
          </div>
          <div>
            <label htmlFor="housing_type" className="block text-sm font-medium text-stone-700 mb-1">Housing Type</label>
            <select id="housing_type" name="housing_type" value={form.housing_type} onChange={handleChange} className={inputCls}>
              <option value="">Select...</option>
              <option value="house">House</option>
              <option value="apartment">Apartment</option>
              <option value="condo">Condo</option>
              <option value="townhouse">Townhouse</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label htmlFor="owns_or_rents" className="block text-sm font-medium text-stone-700 mb-1">Own or Rent</label>
            <select id="owns_or_rents" name="owns_or_rents" value={form.owns_or_rents} onChange={handleChange} className={inputCls}>
              <option value="">Select...</option>
              <option value="own">Own</option>
              <option value="rent">Rent</option>
              <option value="other">Other</option>
            </select>
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


import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchPet, createApplication } from '../services/apiService'
import type { Pet } from '../types'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'

interface ApplicationForm {
  why_adopt: string
  experience_with_pets: string
  living_situation: string
  has_other_pets: boolean
  other_pets_description: string
  references: string
  additional_notes: string
}

const EMPTY: ApplicationForm = {
  why_adopt: '',
  experience_with_pets: '',
  living_situation: '',
  has_other_pets: false,
  other_pets_description: '',
  references: '',
  additional_notes: '',
}

export default function NewApplicationPage() {
  const [searchParams] = useSearchParams()
  const petId = searchParams.get('pet') || ''
  const navigate = useNavigate()
  const [pet, setPet] = useState<Pet | null>(null)
  const [form, setForm] = useState<ApplicationForm>(EMPTY)
  const [loading, setLoading] = useState(petId ? true : false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (petId) {
      fetchPet(petId)
        .then(setPet)
        .catch(() => setError('Could not load pet details.'))
        .finally(() => setLoading(false))
    }
  }, [petId])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = e.target
    setForm((prev) => ({
      ...prev,
      [name]:
        type === 'checkbox'
          ? (e.target as HTMLInputElement).checked
          : value,
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!petId) {
      setError('No pet selected. Please choose a pet to adopt.')
      return
    }
    setSubmitting(true)
    setError('')
    setFieldErrors({})
    try {
      await createApplication(petId, {
        why_adopt: form.why_adopt,
        experience_with_pets: form.experience_with_pets,
        living_situation: form.living_situation,
        has_other_pets: form.has_other_pets,
        other_pets_description: form.other_pets_description,
        references: form.references,
        additional_notes: form.additional_notes,
      })
      navigate('/applications', { state: { created: true } })
    } catch (err: unknown) {
      const anyErr = err as {
        response?: { data?: Record<string, string | string[]> }
      }
      const data = anyErr?.response?.data
      if (data && typeof data === 'object') {
        const flattened: Record<string, string> = {}
        Object.entries(data).forEach(([k, v]) => {
          flattened[k] = Array.isArray(v) ? v.join(' ') : String(v)
        })
        setFieldErrors(flattened)
      } else {
        setError('Failed to submit your application.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Spinner label="Loading pet..." />
  if (error && !pet) return <ErrorState message={error} />

  const inputCls =
    'w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500'

return (
  <div className="mx-auto max-w-3xl px-4 py-8">
    <button
      onClick={() => navigate(-1)}
      className="mb-4 text-sm font-medium text-stone-600 hover:text-stone-900"
    >
      &larr; Back
    </button>
    <h1 className="text-2xl font-semibold text-stone-900">Adoption Application</h1>

    {pet && (
      <div className="mt-4 flex items-center gap-4 rounded-lg border border-stone-200 bg-white p-4">
        {pet.primary_image?.image && (
          <img
            src={pet.primary_image.image}
            alt={pet.name}
            className="h-16 w-16 rounded-lg object-cover"
          />
        )}
        <div>
          <p className="font-medium text-stone-900">{pet.name}</p>
          <p className="text-sm text-stone-600">
            {pet.species} &middot; {pet.breed || 'Mixed breed'} &middot; {pet.age_months}{' '}
            month{pet.age_months === 1 ? '' : 's'}
          </p>
        </div>
      </div>
    )}

    {error && !pet && (
      <div className="mt-4">
        <Alert type="error">{error}</Alert>
      </div>
    )}

    <form onSubmit={handleSubmit} className="mt-6 space-y-5">
      <div>
        <label htmlFor="why_adopt" className="mb-1 block text-sm font-medium text-stone-700">
          Why do you want to adopt this pet?
        </label>
        <textarea
          id="why_adopt"
          name="why_adopt"
          rows={3}
          value={form.why_adopt}
          onChange={handleChange}
          className={inputCls}
          placeholder="Tell us a little about why you'd like to welcome this pet home"
        />
        <FieldError message={fieldErrors.why_adopt} />
      </div>

      <div>
        <label
          htmlFor="experience_with_pets"
          className="mb-1 block text-sm font-medium text-stone-700"
        >
          Experience with pets
        </label>
        <textarea
          id="experience_with_pets"
          name="experience_with_pets"
          rows={3}
          value={form.experience_with_pets}
          onChange={handleChange}
          className={inputCls}
          placeholder="Describe any past or current experience caring for animals"
        />
        <FieldError message={fieldErrors.experience_with_pets} />
      </div>

      <div>
        <label
          htmlFor="living_situation"
          className="mb-1 block text-sm font-medium text-stone-700"
        >
          Living situation
        </label>
        <textarea
          id="living_situation"
          name="living_situation"
          rows={3}
          value={form.living_situation}
          onChange={handleChange}
          className={inputCls}
          placeholder="House, apartment, yard space, other household members"
        />
        <FieldError message={fieldErrors.living_situation} />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="has_other_pets"
          name="has_other_pets"
          type="checkbox"
          checked={form.has_other_pets}
          onChange={handleChange}
          className="h-4 w-4 rounded border-stone-300"
        />
        <label htmlFor="has_other_pets" className="text-sm text-stone-700">
          I currently have other pets
        </label>
      </div>

      {form.has_other_pets && (
        <div>
          <label
            htmlFor="other_pets_description"
            className="mb-1 block text-sm font-medium text-stone-700"
          >
            Describe your other pets
          </label>
          <textarea
            id="other_pets_description"
            name="other_pets_description"
            rows={2}
            value={form.other_pets_description}
            onChange={handleChange}
            className={inputCls}
            placeholder="Types, ages, temperament"
          />
          <FieldError message={fieldErrors.other_pets_description} />
        </div>
      )}

      <div>
        <label htmlFor="references" className="mb-1 block text-sm font-medium text-stone-700">
          References
        </label>
        <textarea
          id="references"
          name="references"
          rows={2}
          value={form.references}
          onChange={handleChange}
          className={inputCls}
          placeholder="Personal or veterinary references"
        />
        <FieldError message={fieldErrors.references} />
      </div>

      <div>
        <label htmlFor="additional_notes" className="mb-1 block text-sm font-medium text-stone-700">
          Additional notes
        </label>
        <textarea
          id="additional_notes"
          name="additional_notes"
          rows={2}
          value={form.additional_notes}
          onChange={handleChange}
          className={inputCls}
          placeholder="Anything else you'd like us to know"
        />
        <FieldError message={fieldErrors.additional_notes} />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-orange-700 disabled:opacity-50"
      >
        {submitting ? 'Submitting...' : 'Submit Application'}
      </button>
    </form>
  </div>
)
}


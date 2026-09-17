import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { createApplication, fetchPet } from '../services/apiService'
import type { Application, Pet } from '../types'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'
import { capitalize, getStatusColor } from '../utils/format'

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

/**
 * Document slots shown inside the application. The two required slots mirror
 * REQUIRED_DOCUMENT_TYPES in backend/apps/documents/serializers.py.
 */
const DOCUMENT_SLOTS = [
  {
    type: 'identification',
    label: 'Valid ID',
    required: true,
    hint: 'Government-issued ID (passport, driver’s licence, national ID)',
  },
  {
    type: 'proof_of_address',
    label: 'Proof of Address',
    required: true,
    hint: 'Recent utility bill, lease, or bank statement',
  },
  {
    type: 'vet_reference',
    label: 'Supporting Document',
    required: false,
    hint: 'Optional — veterinary reference or similar supporting document',
  },
]

const ACCEPTED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt']
const MAX_FILE_SIZE = 10 * 1024 * 1024

const STEPS = ['Application', 'Documents', 'Review'] as const

export default function NewApplicationPage() {
  const [searchParams] = useSearchParams()
  const petId = searchParams.get('pet') || ''
  const navigate = useNavigate()

  const [pet, setPet] = useState<Pet | null>(null)
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<ApplicationForm>(EMPTY)
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [loading, setLoading] = useState(petId ? true : false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [documentErrors, setDocumentErrors] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState<Application | null>(null)

  useEffect(() => {
    if (petId) {
      fetchPet(petId)
        .then(setPet)
        .catch(() => setError('Could not load pet details.'))
        .finally(() => setLoading(false))
    }
  }, [petId])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }))
  }

  /** Client-side mirror of the backend file rules, so problems surface early. */
  const validateFile = (file: File): string => {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
    if (!ACCEPTED_EXTENSIONS.includes(ext)) return `File type '${ext || 'unknown'}' is not allowed.`
    if (file.size > MAX_FILE_SIZE) return 'File size exceeds 10MB limit.'
    return ''
  }

  const handleFileChange = (docType: string, file: File | null) => {
    setFiles((prev) => ({ ...prev, [docType]: file }))
    setDocumentErrors((prev) => {
      const next = { ...prev }
      const message = file ? validateFile(file) : ''
      if (message) next[docType] = message
      else delete next[docType]
      return next
    })
  }

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}
    if (!form.why_adopt.trim()) errors.why_adopt = 'Please tell us why you want to adopt this pet.'
    if (!form.experience_with_pets.trim()) errors.experience_with_pets = 'Please describe your experience with pets.'
    if (!form.living_situation.trim()) errors.living_situation = 'Please describe your living situation.'
    if (form.has_other_pets && !form.other_pets_description.trim()) {
      errors.other_pets_description = 'Please describe the other pets in your home.'
    }
    if (!form.references.trim()) errors.references = 'Please provide at least one reference.'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const validateDocuments = (): boolean => {
    const errors: Record<string, string> = {}
    DOCUMENT_SLOTS.forEach((slot) => {
      const file = files[slot.type]
      if (!file) {
        if (slot.required) errors[slot.type] = `${slot.label} is required before you can submit.`
        return
      }
      const message = validateFile(file)
      if (message) errors[slot.type] = message
    })
    setDocumentErrors(errors)
    return Object.keys(errors).length === 0
  }

  const goNext = () => {
    setError('')
    if (step === 0 && !validateForm()) return
    if (step === 1 && !validateDocuments()) return
    setStep((s) => Math.min(s + 1, STEPS.length - 1))
  }

  const goBack = () => {
    setError('')
    setStep((s) => Math.max(s - 1, 0))
  }

  const handleSubmit = async () => {
    if (!petId) {
      setError('No pet selected. Please choose a pet to adopt.')
      return
    }
    if (!validateForm()) {
      setError('Some required information is missing. Please review the application.')
      setStep(0)
      return
    }
    if (!validateDocuments()) {
      setError('Some required documents are missing or invalid.')
      setStep(1)
      return
    }

    setSubmitting(true)
    setError('')
    try {
      const documents = DOCUMENT_SLOTS.filter((slot) => files[slot.type]).map((slot) => ({
        document_type: slot.type,
        file: files[slot.type] as File,
      }))
      const created = await createApplication(petId, { ...form }, documents)
      setSubmitted(created as Application)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: Record<string, unknown> } }
      const data = anyErr?.response?.data
      if (data && typeof data === 'object') {
        const docErrors = data.documents
        if (docErrors && typeof docErrors === 'object' && !Array.isArray(docErrors)) {
          const flattened: Record<string, string> = {}
          Object.entries(docErrors as Record<string, unknown>).forEach(([key, value]) => {
            flattened[key] = Array.isArray(value) ? String(value[0]) : String(value)
          })
          setDocumentErrors(flattened)
          setError('Please fix the problems with your documents and submit again.')
          setStep(1)
        } else {
          const flattened: Record<string, string> = {}
          Object.entries(data).forEach(([key, value]) => {
            flattened[key] = Array.isArray(value) ? value.join(' ') : String(value)
          })
          setFieldErrors(flattened)
          setError(
            typeof docErrors === 'string'
              ? docErrors
              : 'Your application could not be submitted. Please review the highlighted fields.'
          )
          if (!docErrors) setStep(0)
        }
      } else {
        setError('Failed to submit your application. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Spinner label="Loading pet..." />
  if (error && !pet && !submitted) return <ErrorState message={error} />

  const inputCls =
    'w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500'

  if (submitted) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="rounded-lg border border-orange-100 bg-white p-6 shadow-sm">
          <Alert type="success">
            <strong>Application submitted successfully.</strong> We&apos;ll let you know once it has been reviewed.
          </Alert>

          <dl className="mt-6 space-y-3 text-sm">
            <div className="flex gap-2">
              <dt className="w-24 font-semibold text-stone-700">Pet</dt>
              <dd className="text-stone-600">{submitted.pet_name || pet?.name}</dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="w-24 font-semibold text-stone-700">Status</dt>
              <dd>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${getStatusColor(submitted.status)}`}>
                  {capitalize(submitted.status)}
                </span>
              </dd>
            </div>
          </dl>

          <h2 className="mt-6 text-sm font-semibold text-stone-700">Documents</h2>
          <ul className="mt-2 space-y-1 text-sm text-stone-600">
            {(submitted.documents ?? []).map((doc) => (
              <li key={doc.id}>
                <span className="text-green-600" aria-hidden="true">
                  ✓
                </span>{' '}
                {capitalize(doc.document_type)} — {doc.original_filename}
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to={`/applications/${submitted.id}`}
              className="rounded-md bg-orange-600 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-700"
            >
              View application
            </Link>
            <Link
              to="/applications"
              className="rounded-md bg-stone-100 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-200"
            >
              My Applications
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => navigate(-1)} className="mb-4 text-sm font-medium text-stone-600 hover:text-stone-900">
        &larr; Back
      </button>
      <h1 className="text-2xl font-semibold text-stone-900">Adoption Application</h1>

      {pet && (
        <div className="mt-4 flex items-center gap-4 rounded-lg border border-stone-200 bg-white p-4">
          {pet.primary_image?.image && (
            <img src={pet.primary_image.image} alt={pet.name} className="h-16 w-16 rounded-lg object-cover" />
          )}
          <div>
            <p className="font-medium text-stone-900">{pet.name}</p>
            <p className="text-sm text-stone-600">
              {pet.species} &middot; {pet.breed || 'Mixed breed'} &middot; {pet.age_months} month
              {pet.age_months === 1 ? '' : 's'}
            </p>
          </div>
        </div>
      )}

      {!petId && (
        <div className="mt-4">
          <Alert type="error">
            No pet selected.{' '}
            <Link to="/pets" className="underline">
              Browse pets
            </Link>{' '}
            and choose one to adopt.
          </Alert>
        </div>
      )}

      <ol className="mt-6 flex flex-wrap items-center gap-2 text-sm" aria-label="Application steps">
        {STEPS.map((label, index) => (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                index === step
                  ? 'bg-orange-600 text-white'
                  : index < step
                    ? 'bg-orange-100 text-orange-700'
                    : 'bg-stone-100 text-stone-500'
              }`}
              aria-current={index === step ? 'step' : undefined}
            >
              {index < step ? '✓' : index + 1}
            </span>
            <span className={index === step ? 'font-medium text-stone-800' : 'text-stone-500'}>{label}</span>
            {index < STEPS.length - 1 && <span className="text-stone-300">—</span>}
          </li>
        ))}
      </ol>

      {error && (
        <div className="mt-4">
          <Alert type="error">{error}</Alert>
        </div>
      )}

      <div className="mt-6 rounded-lg border border-orange-100 bg-white p-6 shadow-sm">
        {step === 0 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold text-stone-800">Applicant Information</h2>
            <div>
              <label htmlFor="why_adopt" className="mb-1 block text-sm font-medium text-stone-700">
                Why do you want to adopt this pet? <span className="text-red-600">*</span>
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
              <label htmlFor="experience_with_pets" className="mb-1 block text-sm font-medium text-stone-700">
                Experience with pets <span className="text-red-600">*</span>
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

            <h2 className="pt-2 text-lg font-semibold text-stone-800">Application Details</h2>
            <div>
              <label htmlFor="living_situation" className="mb-1 block text-sm font-medium text-stone-700">
                Living situation <span className="text-red-600">*</span>
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
                <label htmlFor="other_pets_description" className="mb-1 block text-sm font-medium text-stone-700">
                  Describe your other pets <span className="text-red-600">*</span>
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
                References <span className="text-red-600">*</span>
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
          </div>
        )}

        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-stone-800">Required Documents</h2>
              <p className="mt-1 text-sm text-stone-500">
                Accepted: PDF, images, DOC/DOCX, TXT. Max 10MB each. These are submitted together with your
                application.
              </p>
            </div>

            {DOCUMENT_SLOTS.map((slot) => (
              <div key={slot.type} className="rounded-md border border-stone-200 p-4">
                <label htmlFor={`file-${slot.type}`} className="block text-sm font-medium text-stone-700">
                  {slot.label} {slot.required && <span className="text-red-600">*</span>}
                </label>
                <p className="mt-0.5 text-xs text-stone-500">{slot.hint}</p>
                <input
                  id={`file-${slot.type}`}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(',')}
                  onChange={(e) => handleFileChange(slot.type, e.target.files?.[0] ?? null)}
                  className="mt-2 w-full text-sm text-stone-600 file:mr-4 file:rounded-md file:border-0 file:bg-orange-100 file:px-4 file:py-2 file:text-orange-700 hover:file:bg-orange-200"
                />
                {files[slot.type] && !documentErrors[slot.type] && (
                  <p className="mt-2 text-sm text-green-700">
                    <span aria-hidden="true">✓</span> {files[slot.type]?.name} (
                    {((files[slot.type]?.size ?? 0) / 1024).toFixed(1)} KB)
                  </p>
                )}
                <FieldError message={documentErrors[slot.type]} />
              </div>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold text-stone-800">Review Your Information</h2>

            <ReviewItem label="Pet" value={pet?.name || '—'} />
            <ReviewItem label="Why adopt" value={form.why_adopt} />
            <ReviewItem label="Experience with pets" value={form.experience_with_pets} />
            <ReviewItem label="Living situation" value={form.living_situation} />
            <ReviewItem label="Other pets" value={form.has_other_pets ? form.other_pets_description || 'Yes' : 'No'} />
            <ReviewItem label="References" value={form.references} />
            {form.additional_notes && <ReviewItem label="Additional notes" value={form.additional_notes} />}

            <div className="border-t border-stone-100 pt-4">
              <h3 className="text-sm font-semibold text-stone-700">Documents</h3>
              <ul className="mt-2 space-y-1 text-sm text-stone-600">
                {DOCUMENT_SLOTS.map((slot) => {
                  const file = files[slot.type]
                  return (
                    <li key={slot.type}>
                      <span className={file ? 'text-green-600' : 'text-stone-400'} aria-hidden="true">
                        {file ? '✓' : '—'}
                      </span>{' '}
                      {slot.label}: {file ? file.name : slot.required ? 'Missing' : 'Not provided (optional)'}
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-stone-100 pt-5">
          {step > 0 && (
            <button
              type="button"
              onClick={goBack}
              disabled={submitting}
              className="rounded-md bg-stone-100 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-200 disabled:opacity-50"
            >
              Back
            </button>
          )}
          {step < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={goNext}
              className="rounded-md bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-orange-700"
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !petId}
              className="rounded-md bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-orange-700 disabled:opacity-50"
            >
              {submitting ? 'Submitting...' : 'Submit Application'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-stone-100 pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold text-stone-700">{label}</h3>
      <p className="mt-1 whitespace-pre-line text-sm text-stone-600">{value || '—'}</p>
    </div>
  )
}

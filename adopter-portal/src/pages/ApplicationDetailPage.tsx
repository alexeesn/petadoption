import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchApplication, cancelApplication, uploadDocument } from '../services/apiService'
import type { Application } from '../types'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'
import { formatDate, getStatusColor, capitalize } from '../utils/format'

const ACCEPTED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt']
const MAX_FILE_SIZE = 10 * 1024 * 1024

/** Statuses where staff have explicitly asked the adopter for more paperwork. */
const DOCUMENTS_REQUESTED = ['pending_documents', 'additional_info_requested']

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [app, setApp] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [notice, setNotice] = useState('')
  const [extraType, setExtraType] = useState('other')
  const [extraFile, setExtraFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (!id) return
    fetchApplication(id)
      .then(setApp)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  const handleCancel = async () => {
    if (!id || !window.confirm('Are you sure you want to cancel this application?')) return
    setCancelling(true)
    setNotice('')
    try {
      const updated = await cancelApplication(id)
      setApp(updated)
      setNotice('Application cancelled.')
    } catch {
      setNotice('Could not cancel the application.')
    } finally {
      setCancelling(false)
    }
  }

  const handleExtraUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !extraFile) {
      setUploadError('Please choose a file to upload.')
      return
    }
    const ext = extraFile.name.includes('.') ? `.${extraFile.name.split('.').pop()?.toLowerCase()}` : ''
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setUploadError(`File type '${ext || 'unknown'}' is not allowed.`)
      return
    }
    if (extraFile.size > MAX_FILE_SIZE) {
      setUploadError('File size exceeds 10MB limit.')
      return
    }

    setUploading(true)
    setUploadError('')
    try {
      await uploadDocument(id, extraFile, extraType)
      const refreshed = await fetchApplication(id)
      setApp(refreshed)
      setExtraFile(null)
      setNotice('Document uploaded and attached to this application.')
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: Record<string, string[] | string> } }
      const detail = anyErr?.response?.data?.file
      setUploadError(
        Array.isArray(detail) ? detail[0] : typeof detail === 'string' ? detail : 'Failed to upload document.'
      )
    } finally {
      setUploading(false)
    }
  }

  if (loading) return <Spinner label="Loading application..." />
  if (error) return <ErrorState message="Could not load this application." />
  if (!app) return null

  const documents = app.documents ?? []
  const canRequestChanges = ['draft', 'submitted', 'pending_documents', 'additional_info_requested'].includes(
    app.status
  )

  return (
    <div className="max-w-3xl">
      <Link to="/applications" className="text-orange-600 text-sm font-medium hover:underline">
        ← Back to applications
      </Link>

      <div className="mt-4 bg-white rounded-lg shadow-sm border border-orange-100 p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-stone-800">Application for {app.pet_name}</h1>
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(app.status)}`}>
            {capitalize(app.status)}
          </span>
        </div>
        <p className="mt-2 text-sm text-stone-500">Submitted {formatDate(app.created_at)}</p>

        {notice && (
          <div className="mt-4">
            <Alert type="success">{notice}</Alert>
          </div>
        )}

        {app.rejection_reason && (
          <div className="mt-4">
            <Alert type="error">
              <strong>Reason:</strong> {app.rejection_reason}
            </Alert>
          </div>
        )}

        <div className="mt-6 space-y-5">
          <Section title="Why you want to adopt">
            <p className="text-stone-600 whitespace-pre-line">{app.why_adopt || '—'}</p>
          </Section>
          <Section title="Experience with pets">
            <p className="text-stone-600 whitespace-pre-line">{app.experience_with_pets || '—'}</p>
          </Section>
          <Section title="Living situation">
            <p className="text-stone-600 whitespace-pre-line">{app.living_situation || '—'}</p>
          </Section>
          <Section title="Other pets">
            <p className="text-stone-600">{app.has_other_pets ? app.other_pets_description || 'Yes' : 'No'}</p>
          </Section>
          <Section title="References">
            <p className="text-stone-600 whitespace-pre-line">{app.references || '—'}</p>
          </Section>
          {app.additional_notes && (
            <Section title="Additional notes">
              <p className="text-stone-600 whitespace-pre-line">{app.additional_notes}</p>
            </Section>
          )}

          <Section title="Uploaded documents">
            {documents.length === 0 ? (
              <p className="text-stone-500">No documents attached to this application.</p>
            ) : (
              <ul className="space-y-2">
                {documents.map((doc) => (
                  <li key={doc.id} className="flex flex-wrap items-center gap-2 text-stone-600">
                    <span className="text-green-600" aria-hidden="true">
                      ✓
                    </span>
                    <span className="font-medium text-stone-700">{capitalize(doc.document_type)}</span>
                    <span className="text-stone-500">— {doc.original_filename}</span>
                    {doc.download_url && (
                      <a href={doc.download_url} className="text-orange-600 hover:underline">
                        Download
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        {DOCUMENTS_REQUESTED.includes(app.status) && (
          <div className="mt-6 rounded-md border border-orange-200 bg-orange-50 p-4">
            <h3 className="text-sm font-semibold text-stone-800">Add a requested document</h3>
            <p className="mt-1 text-xs text-stone-600">
              Staff asked for more information on this application. Uploads here are attached to it directly.
            </p>
            <form onSubmit={handleExtraUpload} className="mt-3 space-y-3">
              <div>
                <label htmlFor="extraType" className="block text-sm font-medium text-stone-700 mb-1">
                  Document type
                </label>
                <select
                  id="extraType"
                  value={extraType}
                  onChange={(e) => setExtraType(e.target.value)}
                  className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  <option value="identification">Identification</option>
                  <option value="proof_of_address">Proof of Address</option>
                  <option value="income_proof">Income Proof</option>
                  <option value="vet_reference">Veterinary Reference</option>
                  <option value="personal_reference">Personal Reference</option>
                  <option value="home_photos">Home Photos</option>
                  <option value="lease_agreement">Lease Agreement</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label htmlFor="extraFile" className="block text-sm font-medium text-stone-700 mb-1">
                  File
                </label>
                <input
                  id="extraFile"
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(',')}
                  onChange={(e) => {
                    setExtraFile(e.target.files?.[0] ?? null)
                    setUploadError('')
                  }}
                  className="w-full text-sm text-stone-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-orange-100 file:text-orange-700 hover:file:bg-orange-200"
                />
                <p className="text-xs text-stone-500 mt-1">Accepted: PDF, images, DOC/DOCX, TXT. Max 10MB.</p>
              </div>
              <FieldError message={uploadError} />
              <button
                type="submit"
                disabled={!extraFile || uploading}
                className="px-4 py-2 bg-orange-600 text-white text-sm rounded-md hover:bg-orange-700 disabled:opacity-50"
              >
                {uploading ? 'Uploading...' : 'Upload document'}
              </button>
            </form>
          </div>
        )}

        {canRequestChanges && (
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="px-4 py-2 bg-stone-100 text-stone-700 text-sm font-medium rounded-md hover:bg-stone-200 disabled:opacity-50"
            >
              {cancelling ? 'Cancelling...' : 'Cancel application'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-stone-100 pt-4">
      <h3 className="text-sm font-semibold text-stone-700">{title}</h3>
      <div className="mt-2 text-sm">{children}</div>
    </div>
  )
}

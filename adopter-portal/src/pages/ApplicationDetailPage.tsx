import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchApplication, cancelApplication } from '../services/apiService'
import type { Application } from '../types'
import { Spinner, ErrorState, Alert } from '../components/UI'
import { formatDate, getStatusColor, capitalize } from '../utils/format'

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [app, setApp] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [notice, setNotice] = useState('')

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

  if (loading) return <Spinner label="Loading application..." />
  if (error) return <ErrorState message="Could not load this application." />
  if (!app) return null

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

        {notice && <div className="mt-4"><Alert type="success">{notice}</Alert></div>}

        {app.rejection_reason && (
          <div className="mt-4"><Alert type="error"><strong>Reason:</strong> {app.rejection_reason}</Alert></div>
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
            <p className="text-stone-600">
              {app.has_other_pets ? (app.other_pets_description || 'Yes') : 'No'}
            </p>
          </Section>
          <Section title="References">
            <p className="text-stone-600 whitespace-pre-line">{app.references || '—'}</p>
          </Section>
          {app.additional_notes && (
            <Section title="Additional notes">
              <p className="text-stone-600 whitespace-pre-line">{app.additional_notes}</p>
            </Section>
          )}
        </div>

        {(app.status === 'draft' || app.status === 'submitted' || app.status === 'pending_documents' || app.status === 'additional_info_requested') && (
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to={`/documents`}
              className="px-4 py-2 bg-orange-600 text-white text-sm font-medium rounded-md hover:bg-orange-700"
            >
              Upload documents
            </Link>
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

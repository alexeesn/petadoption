import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchAdoptionRecord } from '../services/apiService'
import { Spinner, ErrorState, EmptyState } from '../components/UI'
import type { AdoptionRecord } from '../types'

export default function AdoptionRecordPage() {
  const { id } = useParams<{ id: string }>()
  const [record, setRecord] = useState<AdoptionRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchAdoptionRecord(id)
      setRecord(data)
    } catch {
      setError('Unable to load adoption record.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <Spinner />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!record) return <EmptyState message="Adoption record not found." />

  const statusColor =
    record.status === 'completed' ? 'bg-green-100 text-green-800'
    : record.status === 'scheduled' ? 'bg-blue-100 text-blue-800'
    : 'bg-purple-100 text-purple-800'

  return (
    <div>
      <Link to="/dashboard" className="text-sm text-orange-600 hover:text-orange-700 mb-4 inline-block">
        ← Back to Dashboard
      </Link>
      <h1 className="text-2xl font-bold text-stone-800 mb-2">Adoption Record</h1>
      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${statusColor}`}>
        {record.status.replace(/_/g, ' ')}
      </span>

      <div className="mt-6 bg-white rounded-lg shadow-sm border border-orange-100 p-6 max-w-2xl space-y-4">
        <div>
          <p className="text-sm text-stone-500">Pet</p>
          <p className="text-lg font-semibold text-stone-800">{record.pet_name}</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-stone-500">Adoption Date</p>
            <p className="text-stone-800">{record.adoption_date ? new Date(record.adoption_date).toLocaleDateString() : '—'}</p>
          </div>
          <div>
            <p className="text-sm text-stone-500">Completed Date</p>
            <p className="text-stone-800">{record.completed_date ? new Date(record.completed_date).toLocaleDateString() : '—'}</p>
          </div>
        </div>
        {record.notes && (
          <div>
            <p className="text-sm text-stone-500">Notes</p>
            <p className="text-stone-700">{record.notes}</p>
          </div>
        )}
        {record.return_reason && (
          <div>
            <p className="text-sm text-stone-500">Return Reason</p>
            <p className="text-stone-700">{record.return_reason}</p>
          </div>
        )}
        {record.status === 'scheduled' && (
          <div className="bg-blue-50 border border-blue-100 rounded-md p-4 text-sm text-blue-800">
            Your adoption is scheduled. Please follow the instructions provided by our staff.
          </div>
        )}
        {record.status === 'completed' && (
          <div className="bg-green-50 border border-green-100 rounded-md p-4 text-sm text-green-800">
            Congratulations on your new family member! 🎉
          </div>
        )}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchApplications } from '../services/apiService'
import type { Application } from '../types'
import { Spinner, ErrorState, EmptyState } from '../components/UI'
import { formatDate, getStatusColor, capitalize } from '../utils/format'

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchApplications()
      .then((data) => {
        const appData = Array.isArray(data) ? data : (data as { results?: Application[] }).results || []
        setApplications(appData)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner label="Loading applications..." />
  if (error) return <ErrorState message="Could not load your applications." />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-stone-800">My Applications</h1>
        <Link
          to="/pets"
          className="px-4 py-2 bg-orange-600 text-white text-sm font-medium rounded-md hover:bg-orange-700"
        >
          Browse pets
        </Link>
      </div>

      {applications.length === 0 ? (
        <EmptyState
          message="You haven't applied to adopt any pets yet."
          action={
            <Link to="/pets" className="px-4 py-2 bg-orange-600 text-white text-sm rounded-md">
              Find a pet to adopt
            </Link>
          }
        />
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-orange-100 overflow-hidden">
          <div className="hidden md:grid grid-cols-12 gap-4 px-5 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wide">
            <span className="col-span-3">Pet</span>
            <span className="col-span-2">Status</span>
            <span className="col-span-3">Submitted</span>
            <span className="col-span-2">Last updated</span>
            <span className="col-span-2"></span>
          </div>
          <ul className="divide-y divide-stone-100">
            {applications.map((app) => (
              <li key={app.id} className="px-5 py-4 hover:bg-orange-50/50">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 items-center">
                  <div className="col-span-3">
                    <p className="font-medium text-stone-800">{app.pet_name}</p>
                    <p className="text-xs text-stone-500 md:hidden">{formatDate(app.created_at)}</p>
                  </div>
                  <div className="col-span-2">
                    <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${getStatusColor(app.status)}`}>
                      {capitalize(app.status)}
                    </span>
                  </div>
                  <div className="col-span-3 text-sm text-stone-500 hidden md:block">{formatDate(app.created_at)}</div>
                  <div className="col-span-2 text-sm text-stone-500 hidden md:block">{formatDate(app.updated_at)}</div>
                  <div className="col-span-2 text-right">
                    <Link to={`/applications/${app.id}`} className="text-sm text-orange-600 hover:underline font-medium">
                      View details
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

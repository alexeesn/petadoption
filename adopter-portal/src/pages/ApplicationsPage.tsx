import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchApplications } from '../services/apiService'
import type { Application } from '../types'
import { Spinner, ErrorState, EmptyState } from '../components/UI'
import { Icon } from '../components/Icons'
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
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-3xl font-extrabold text-primary-900 sm:text-4xl">My Applications</h1>
        <Link to="/pets" className="btn btn-primary">
          Browse pets
        </Link>
      </div>

      {applications.length === 0 ? (
        <EmptyState
          message="You haven't applied to adopt any pets yet."
          action={
            <Link to="/pets" className="btn btn-accent">
              Find a pet to adopt
            </Link>
          }
        />
      ) : (
        <div className="panel overflow-hidden">
          <div className="hidden grid-cols-12 gap-4 border-b border-stone-200 bg-stone-50 px-6 py-3 text-xs font-semibold text-stone-500 md:grid">
            <span className="col-span-3">Pet</span>
            <span className="col-span-2">Status</span>
            <span className="col-span-3">Submitted</span>
            <span className="col-span-2">Last updated</span>
            <span className="col-span-2"></span>
          </div>
          <ul className="divide-y divide-stone-100">
            {applications.map((app) => (
              <li key={app.id} className="px-6 py-4 transition-colors hover:bg-primary-50/60">
                <div className="grid grid-cols-1 items-center gap-2 md:grid-cols-12 md:gap-4">
                  <div className="col-span-3">
                    <p className="font-display text-lg font-semibold text-primary-900">{app.pet_name}</p>
                    <p className="text-xs text-stone-500 md:hidden">{formatDate(app.created_at)}</p>
                  </div>
                  <div className="col-span-2">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${getStatusColor(app.status)}`}>
                      {capitalize(app.status)}
                    </span>
                  </div>
                  <div className="col-span-3 hidden text-sm text-stone-500 md:block">{formatDate(app.created_at)}</div>
                  <div className="col-span-2 hidden text-sm text-stone-500 md:block">{formatDate(app.updated_at)}</div>
                  <div className="col-span-2 md:text-right">
                    <Link
                      to={`/applications/${app.id}`}
                      className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-700 hover:text-primary-900"
                    >
                      {app.status === 'approved' ? 'Choose appointment date' : 'View details'}
                      <Icon name="arrowRight" className="h-4 w-4" />
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

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { fetchApplications, fetchNotifications } from '../services/apiService'
import type { Application, Notification } from '../types'
import { Spinner, ErrorState, EmptyState } from '../components/UI'
import { formatDate, getStatusColor, capitalize } from '../utils/format'

export default function DashboardPage() {
  const { user } = useAuth()
  const [applications, setApplications] = useState<Application[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    Promise.all([fetchApplications(), fetchNotifications()])
      .then(([apps, notifs]) => {
        const appData = Array.isArray(apps) ? apps : (apps as { results?: Application[] }).results || []
        const notifData = Array.isArray(notifs) ? notifs : (notifs as { results?: Notification[] }).results || []
        setApplications(appData)
        setNotifications(notifData)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner label="Loading dashboard..." />
  if (error) return <ErrorState message="Could not load your dashboard." />

  const activeApps = applications.filter((a) => !['rejected', 'cancelled', 'adoption_completed'].includes(a.status))
  const unread = notifications.filter((n) => !n.is_read)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-800">Welcome back, {user?.first_name || 'friend'}!</h1>
        <p className="mt-1 text-stone-500">Here&apos;s a snapshot of your adoption journey.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Active applications" value={activeApps.length} />
        <StatCard label="Total applications" value={applications.length} />
        <StatCard label="Unread notifications" value={unread.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white rounded-lg shadow-sm border border-orange-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-stone-800">Recent applications</h2>
            <Link to="/applications" className="text-sm text-orange-600 hover:underline">View all</Link>
          </div>
          {applications.length === 0 ? (
            <EmptyState message="You haven't applied to any pets yet." />
          ) : (
            <ul className="divide-y divide-stone-100">
              {applications.slice(0, 4).map((app) => (
                <li key={app.id}>
                  <Link to={`/applications/${app.id}`} className="flex items-center justify-between py-3 hover:bg-stone-50 rounded-md px-2 -mx-2">
                    <div>
                      <p className="font-medium text-stone-800">{app.pet_name}</p>
                      <p className="text-xs text-stone-500">{formatDate(app.created_at)}</p>
                    </div>
                    <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${getStatusColor(app.status)}`}>
                      {capitalize(app.status)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-orange-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-stone-800">Notifications</h2>
            <Link to="/notifications" className="text-sm text-orange-600 hover:underline">View all</Link>
          </div>
          {notifications.length === 0 ? (
            <EmptyState message="You're all caught up!" />
          ) : (
            <ul className="divide-y divide-stone-100">
              {notifications.slice(0, 4).map((n) => (
                <li key={n.id} className="py-3">
                  <p className={`font-medium text-stone-800 ${n.is_read ? '' : 'font-semibold'}`}>{n.title}</p>
                  <p className="text-sm text-stone-500 line-clamp-2">{n.message}</p>
                  <p className="text-xs text-stone-400 mt-1">{formatDate(n.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-5">
      <p className="text-3xl font-bold text-orange-600">{value}</p>
      <p className="mt-1 text-sm text-stone-500">{label}</p>
    </div>
  )
}

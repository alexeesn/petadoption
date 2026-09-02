import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchNotifications, markNotificationRead, markAllNotificationsRead } from '../services/apiService'
import { Spinner, EmptyState, ErrorState } from '../components/UI'
import type { Notification } from '../types'

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchNotifications()
      setNotifications(Array.isArray(data) ? data : data.results ?? [])
    } catch {
      setError('Unable to load notifications.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id)
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    } catch {
      // ignore
    }
  }

  const handleMarkAll = async () => {
    try {
      await markAllNotificationsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold text-stone-800">Notifications</h1>
        {notifications.some((n) => !n.is_read) && (
          <button
            onClick={handleMarkAll}
            className="text-sm text-orange-600 hover:text-orange-700 font-medium"
          >
            Mark all as read
          </button>
        )}
      </div>
      <p className="text-stone-500 mb-6">Stay updated on your applications and adoptions.</p>

      {error && <div className="mb-4"><ErrorState message={error} onRetry={load} /></div>}

      {loading ? (
        <Spinner />
      ) : notifications.length === 0 ? (
        <EmptyState message="You're all caught up! No notifications." />
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`bg-white rounded-lg shadow-sm border p-4 ${
                n.is_read ? 'border-stone-100' : 'border-orange-200'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className={`font-medium ${n.is_read ? 'text-stone-600' : 'text-stone-800'}`}>
                    {n.title}
                  </p>
                  <p className="text-sm text-stone-500 mt-1">{n.message}</p>
                  <p className="text-xs text-stone-400 mt-2">{new Date(n.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {n.link && (
                    <Link to={n.link} className="text-sm text-orange-600 hover:text-orange-700">
                      View
                    </Link>
                  )}
                  {!n.is_read && (
                    <button
                      onClick={() => handleMarkRead(n.id)}
                      className="text-xs text-stone-400 hover:text-stone-600"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { notificationService } from '../services/apiService'
import { Loading as Spinner } from '../components/UI'
import { Icon } from '../components/Icons'
import type { Notification } from '../types'

export default function NotificationsPage() {
  const [notices, setNotices] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [page, setPage] = useState(1)
  const [next, setNext] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await notificationService.list({ page })
      setNotices(Array.isArray(data) ? data : data.results)
      setNext(!Array.isArray(data) && Boolean(data.next))
    } catch { setError('Could not load notifications. Please try again.') }
    finally { setLoading(false) }
  }, [page])
  useEffect(() => { void load() }, [load])
  async function read(id: string) {
    try {
      await notificationService.markRead(id)
      setNotices(rows => rows.map(item => item.id === id ? { ...item, is_read: true } : item))
      window.dispatchEvent(new Event('pawconnect-notifications-changed'))
      setActionError('')
    } catch { setActionError('Could not mark the notification read. Please try again.') }
  }
  async function readAll() {
    try {
      await notificationService.markAllRead()
      setNotices(rows => rows.map(item => ({ ...item, is_read: true })))
      window.dispatchEvent(new Event('pawconnect-notifications-changed'))
      setActionError('')
    } catch { setActionError('Could not mark notifications read. Please try again.') }
  }
  return <div className="mx-auto max-w-5xl">
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4"><div><p className="section-label mb-3">Your inbox</p><h1 className="text-3xl font-bold text-primary-900">Notifications</h1><p className="mt-3 text-sm text-stone-600">Keep up with the latest updates in your workspace.</p></div><button type="button" onClick={() => { void readAll() }} className="btn btn-secondary">Mark all as read</button></div>
    {actionError && <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{actionError}</p>}
    {loading ? <Spinner label="Loading notifications..." /> : error ? <div role="alert" className="panel p-6"><p className="text-sm text-red-700">{error}</p><button type="button" className="btn btn-secondary mt-4" onClick={() => { void load() }}>Try again</button></div> : notices.length === 0 ? <div className="panel p-12 text-center"><Icon name="bell" className="mx-auto mb-4 h-8 w-8 text-stone-400"/><h2 className="text-xl font-semibold text-stone-900">All caught up.</h2><p className="mt-3 text-sm text-stone-500">Your notifications will appear here.</p></div> : <div className="space-y-3">{notices.map(notice => {
      const safe = notice.link?.startsWith('/') && !notice.link.startsWith('//')
      return <article key={notice.id} className={`panel flex items-start gap-4 p-5 sm:p-6 ${notice.is_read ? '' : 'border-primary-200'}`}><span className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-700"><Icon name="bell" className="h-4 w-4"/></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-bold text-stone-900">{notice.title}</h2><span className="text-[10px] font-semibold uppercase tracking-wider text-stone-500">{notice.is_read ? 'Read' : 'Unread'}</span></div><p className="mt-2 whitespace-pre-line break-words text-sm leading-7 text-stone-600">{notice.message}</p><div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs"><time className="text-stone-500" dateTime={notice.created_at}>{new Date(notice.created_at).toLocaleString()}</time>{safe && <Link to={notice.link} onClick={() => { if (!notice.is_read) void read(notice.id) }} className="font-semibold text-primary-700">View update →</Link>}{!notice.is_read && <button type="button" onClick={() => { void read(notice.id) }} className="font-semibold text-stone-600">Mark read</button>}</div></div></article>
    })}</div>}
    {!loading && !error && (next || page > 1) && <div className="mt-6 flex items-center justify-center gap-4"><button type="button" disabled={page === 1} onClick={() => setPage(value => value - 1)} className="btn btn-secondary">Previous</button><span className="text-sm text-stone-500">Page {page}</span><button type="button" disabled={!next} onClick={() => setPage(value => value + 1)} className="btn btn-secondary">Next</button></div>}
  </div>
}

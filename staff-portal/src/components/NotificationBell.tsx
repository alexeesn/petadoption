import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Icon } from './Icons'
import type { Notification } from '../types'
import { notificationService } from '../services/apiService'

export default function NotificationBell({ open, onOpenChange }: { open: boolean; onOpenChange: (value: boolean) => void }) {
  const [unreadCount, setUnreadCount] = useState(0)
  const refreshCount = useCallback(async () => { try { const { data } = await notificationService.unreadCount(); setUnreadCount(data.unread_count) } catch { /* Keep the last verified count. */ } }, [])
  const [notices, setNotices] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const { pathname } = useLocation()
  useEffect(() => { onOpenChange(false) }, [pathname])
  useEffect(() => {
    void refreshCount()
    const interval = window.setInterval(() => { void refreshCount() }, 30000)
    const refresh = () => { void refreshCount() }
    window.addEventListener('pawconnect-notifications-changed', refresh)
    return () => { window.clearInterval(interval); window.removeEventListener('pawconnect-notifications-changed', refresh) }
  }, [refreshCount])
  useEffect(() => {
    if (!open) return
    let active = true
    setLoading(true)
    setError('')
    const load = async () => {
      try {
        const { data } = await notificationService.list()
        if (active) setNotices((Array.isArray(data) ? data : data.results).slice(0, 6))
      } catch { if (active) setError('Could not load notifications. Close and reopen to retry.') }
      finally { if (active) setLoading(false) }
    }
    void load()
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) onOpenChange(false) }
    document.addEventListener('pointerdown', outside)
    return () => { active = false; document.removeEventListener('pointerdown', outside) }
  }, [open])
  async function read(notice: Notification) {
    if (!notice.is_read) {
      try { await notificationService.markRead(notice.id); window.dispatchEvent(new Event('pawconnect-notifications-changed')); void refreshCount() }
      catch { setError('The notification could not be marked read. Its unread count has been kept.') }
    }
    onOpenChange(false)
  }
  return <div ref={root} className="relative" onKeyDown={event => { if (event.key === 'Escape') { onOpenChange(false); trigger.current?.focus() } }}>
    <button ref={trigger} type="button" className="icon-button relative" aria-label={unreadCount ? `Notifications (${unreadCount} unread)` : 'Notifications'} aria-expanded={open} onClick={() => onOpenChange(!open)}>
      <Icon name="bell" className="h-5 w-5" />
      {unreadCount > 0 && <span className="notification-count" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
    </button>
    {open && <div className="popover-panel fixed right-3 top-[5rem] z-50 w-[calc(100vw-1.5rem)] max-w-sm overflow-hidden sm:absolute sm:right-0 sm:top-full sm:mt-3" role="region" aria-label="Recent notifications">
      <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4"><h2 className="text-base font-bold text-stone-900">Notifications</h2><span className="text-xs text-stone-500">{unreadCount} unread</span></div>
      <div className="max-h-[min(26rem,55dvh)] overflow-y-auto">
        {error && <p className="px-5 py-3 text-sm text-red-700" role="alert">{error}</p>}
        {loading ? <p className="p-5 text-sm text-stone-500" role="status">Loading notifications…</p> : notices.length === 0 ? <p className="p-5 text-sm text-stone-500">You’re all caught up. No notifications yet.</p> : notices.map(notice => {
          const safeLink = notice.link?.startsWith('/') && !notice.link.startsWith('//') ? notice.link : '/notifications'
          return <Link key={notice.id} to={safeLink} onClick={() => { void read(notice) }} className={`block border-b border-stone-100 px-5 py-4 transition-colors hover:bg-stone-50 ${notice.is_read ? '' : 'bg-primary-50/60'}`}>
            <div className="flex items-start gap-3"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${notice.is_read ? 'bg-stone-300' : 'bg-primary-600'}`} aria-hidden="true"/><div className="min-w-0"><p className="text-sm font-semibold text-stone-900">{notice.title}</p><p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-600">{notice.message}</p><p className="mt-2 text-[11px] text-stone-500">{new Date(notice.created_at).toLocaleString()}</p></div></div>
          </Link>
        })}
      </div>
      <Link to="/notifications" onClick={() => onOpenChange(false)} className="block px-5 py-3.5 text-center text-sm font-semibold text-primary-700 hover:bg-primary-50">View all notifications</Link>
    </div>}
  </div>
}

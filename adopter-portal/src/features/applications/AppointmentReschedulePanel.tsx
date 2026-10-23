import { useEffect, useState } from 'react'
import type { Appointment, RescheduleRequest } from '../../types'
import { fetchRescheduleRequests, requestAppointmentReschedule } from '../../services/apiService'
import { Alert, Spinner } from '../../components/UI'
import { formatDate, capitalize } from '../../utils/format'
import { useToast } from '../../context/ToastContext'

interface Props {
  applicationId: string
  applicationStatus: string
  appointments: Appointment[]
  onUpdated: () => Promise<void>
}

function todayISO(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function AppointmentReschedulePanel({ applicationId, applicationStatus, appointments, onUpdated }: Props) {
  const toast = useToast()
  const [requests, setRequests] = useState<RescheduleRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loadFailed, setLoadFailed] = useState(false)
  const [notice, setNotice] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [date, setDate] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setLoadFailed(false)
    fetchRescheduleRequests(applicationId)
      .then((data) => { if (active) setRequests(data) })
      .catch(() => { if (active) { setError('Could not load reschedule requests. Please retry before requesting a new date.'); setLoadFailed(true) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [applicationId, refresh])

  const activeAppointment = appointments.find((a) => a.status === 'confirmed' || a.status === 'pending_confirmation')
  const target = applicationStatus !== 'approved' ? undefined
    : activeAppointment?.status === 'confirmed' ? activeAppointment
      : !activeAppointment ? appointments.find((a) => a.status === 'no_show') : undefined
  const pending = requests.find((r) => r.status === 'pending')
  const eligible = applicationStatus === 'approved' && target && !pending

  if (!target && requests.length === 0 && !error && !loading) return null
  return (
    <section aria-label="Appointment rescheduling" className="mt-6 space-y-3 rounded-md border border-primary-200 p-4">
      <h3 className="font-semibold text-primary-900">Appointment rescheduling</h3>
      {notice && <Alert type="success">{notice}</Alert>}
      {error && <div role="alert"><Alert type="error">{error}</Alert>
        {loadFailed && <button type="button" className="btn btn-outline mt-2" disabled={loading || busy} onClick={() => setRefresh((v) => v + 1)}>Retry</button>}
      </div>}
      {loading ? <Spinner label="Loading reschedule requests..." /> : <>
        {target?.status === 'no_show' && <p className="text-sm text-amber-800">
          Your visit on {formatDate(target.requested_date)} was marked as a no-show. {target.no_show_reason}
          {' '}Your adoption has not been cancelled. Request a new date if you wish to continue.
        </p>}
        {pending && <p role="status" className="text-sm text-primary-800">
          Reschedule requested for <strong>{formatDate(pending.requested_date)}</strong>. Waiting for staff review.
          {' '}Your existing appointment remains unchanged until approval.
        </p>}
        {eligible && !loadFailed && <>
          <p className="text-sm text-stone-600">Need another date? Send a request with a reason. Staff will approve or reject it; your confirmed date stays valid until approval.</p>
          <button type="button" className="btn btn-outline" disabled={busy} onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Close request form' : 'Request Reschedule'}
          </button>
          {showForm && <form aria-label="Request appointment reschedule" className="space-y-3" onSubmit={async (event) => {
            event.preventDefault()
            if (!target || busy) return
            const weekday = new Date(`${date}T00:00:00`).getDay()
            if (!date || date < todayISO() || !Number.isFinite(weekday) || weekday === 0 || date === target.requested_date || !reason.trim()) {
              setError('Choose a different date from Monday to Saturday, today onward, and provide a reason.')
              return
            }
            setBusy(true)
            setError('')
            setNotice('')
            try {
              const saved = await requestAppointmentReschedule(target.id, date, reason.trim())
              toast.success('Reschedule requested', 'Your request has been submitted for staff review.')
              setRequests((rows) => [saved, ...rows])
              setShowForm(false)
              setDate('')
              setReason('')
              setNotice('Reschedule request submitted. Staff have been notified; your current appointment is unchanged.')
              onUpdated().catch(() => setNotice('Reschedule request submitted. Refresh the page to reload appointment history.'))
            } catch (err) {
              const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data
              const messages = Object.values(data ?? {}).flatMap((value) => typeof value === 'string' ? [value] : Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [])
              setError(messages.join(' ') || 'Could not submit your reschedule request. Please retry.')
            } finally { setBusy(false) }
          }}>
            <label className="block"><span className="field-label">New appointment date</span>
              <input className="field-input sm:w-64" type="date" min={todayISO()} required disabled={busy}
                value={date} onChange={(e) => { setDate(e.target.value); setError('') }} />
            </label>
            <label className="block"><span className="field-label">Reason for rescheduling</span>
              <textarea className="field-input" required maxLength={2000} rows={3} disabled={busy}
                value={reason} onChange={(e) => { setReason(e.target.value); setError('') }} />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy || !date || !reason.trim()}>
              {busy ? 'Submitting...' : 'Submit Reschedule Request'}
            </button>
          </form>}
        </>}
        {requests.length > 0 && <div className="space-y-3 border-t border-primary-100 pt-3">
          <h4 className="text-sm font-semibold">Reschedule history</h4>
          {requests.map((request) => <div key={request.id} className="text-sm text-stone-700">
            <p>{formatDate(request.original_date)} → {formatDate(request.requested_date)} · <strong>{capitalize(request.status)}</strong></p>
            <p className="whitespace-pre-wrap">Your reason: {request.reason}</p>
            {request.decision_note && <p>{request.decision_note}</p>}
            {request.reviewed_at && <p className="text-xs text-stone-500">Reviewed {new Date(request.reviewed_at).toLocaleString()}</p>}
          </div>)}
        </div>}
      </>}
    </section>
  )
}

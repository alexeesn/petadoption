import { useToast } from '../context/ToastContext'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchApplication, cancelApplication, uploadDocument, fetchAppointments, createAppointment, fetchNotifications } from '../services/apiService'
import type { Application, Appointment } from '../types'
import { Spinner, ErrorState, Alert, FieldError } from '../components/UI'
import { formatDate, getStatusColor, capitalize } from '../utils/format'
import { AppointmentReschedulePanel } from '../features/applications/AppointmentReschedulePanel'

const ACCEPTED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt']
const MAX_FILE_SIZE = 10 * 1024 * 1024

/** Statuses where staff have explicitly asked the adopter for more paperwork. */
const DOCUMENTS_REQUESTED = ['pending_documents', 'additional_info_requested']
const NEXT_STEPS: Record<string, string> = {
  draft: 'This application has not been submitted yet.',
  submitted: 'Your application has been received. Check back here or in notifications for a review update.',
  under_review: 'Your application is being reviewed. We will notify you when there is an update.',
  pending_documents: 'Staff need additional documents. Read their feedback and upload the requested file below.',
  additional_info_requested: 'Staff need more information. Read their feedback and use the requested-document form below where applicable.',
  approved: 'Your application is approved. The visit date still needs separate staff confirmation. Manage your appointment below.',
  rejected: 'Your application was not approved. Read the staff feedback below for the saved reason.',
  cancelled: 'This application is closed. Please contact staff if you have questions.',
  adoption_completed: 'Your adoption is complete. Thank you for giving a pet a new home.',
}

/** Center operating schedule: Monday-Friday, 8:00 AM-5:00 PM. */
const CENTER_SCHEDULE_TEXT = 'Monday to Friday, 8:00 AM - 5:00 PM'

/** Center hours reminder shown with the confirmed-visit preparation list. */
const CENTER_HOURS_TEXT = 'Monday-Friday, 8:00 AM-5:00 PM (except holidays and work suspensions)'

/**
 * Onsite visit guidance shown once the requested visit date is confirmed.
 * These items are brought to the center in person — they are NOT online
 * upload requirements, so the online document workflow is unchanged.
 */
const VISIT_PREPARATION_ITEMS = [
  '1x1 picture',
  'Q.C. ID or valid ID',
  'Photo of your home / space prepared for the pet',
  'Your completed online Adoption Form',
  'Adoption Agreement Form — provided onsite',
]

function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

/** Saturday/Sunday are not selectable; the API enforces this too. */
function isWeekday(dateStr: string): boolean {
  const day = new Date(`${dateStr}T00:00:00`).getDay()
  return day !== 0 && day !== 6
}

export default function ApplicationDetailPage() {
  const toast = useToast()
  const { id } = useParams<{ id: string }>()
  const [app, setApp] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [notice, setNotice] = useState('')
  const [cancelError, setCancelError] = useState('')
  const [extraType, setExtraType] = useState('other')
  const [extraFile, setExtraFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackUnavailable, setFeedbackUnavailable] = useState(false)
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [visitDate, setVisitDate] = useState('')
  const [apptError, setApptError] = useState('')
  const [apptSubmitting, setApptSubmitting] = useState(false)

  useEffect(() => {
    if (!id) return
    let active = true
    setLoading(true)
    setError(false)
    setNotice('')
    setApp(null)
    setAppointments([])
    Promise.all([
      fetchApplication(id),
      // Appointment history for this application (own appointments only).
      fetchAppointments(id),
    ])
      .then(([application, appointments]) => {
        if (!active) return
        setApp(application)
        setAppointments(appointments as Appointment[])
      })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  useEffect(() => {
    setFeedback('')
    setFeedbackUnavailable(false)
    if (!app || !DOCUMENTS_REQUESTED.includes(app.status)) return
    let active = true
    fetchNotifications().then(data => {
      if (!active) return
      const rows = (Array.isArray(data) ? data : data.results) as import('../types').Notification[]
      const notice = rows.find(item => item.link?.split('?')[0] === `/applications/${app.id}` && item.notification_type === 'application')
      setFeedback(notice?.message || '')
    }).catch(() => { if (active) setFeedbackUnavailable(true) })
    return () => { active = false }
  }, [app?.id, app?.status])

  const handleRequestAppointment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    if (!visitDate) {
      setApptError('Please choose a visit date.')
      return
    }
    if (visitDate < todayISO()) {
      setApptError('The visit date cannot be in the past.')
      return
    }
    if (!isWeekday(visitDate)) {
      setApptError('The center only accepts visits Monday to Friday. Please choose a weekday.')
      return
    }
    setApptSubmitting(true)
    setApptError('')
    setNotice('')
    try {
      const appointment = (await createAppointment(id, visitDate)) as Appointment
      setAppointments((prev) => [appointment, ...prev])
      setVisitDate('')
      setNotice('Appointment request submitted. Staff will review your requested date.')
      toast.success('Appointment requested', 'Your requested visit date has been sent to the team for review.')
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: Record<string, string[] | string> } }
      const data = anyErr?.response?.data
      const detail = data?.requested_date ?? data?.application_id ?? data?.error
      setApptError(
        Array.isArray(detail) ? detail[0] : typeof detail === 'string' ? detail : 'Could not submit the appointment request.'
      )
    } finally {
      setApptSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!id || !window.confirm('Are you sure you want to cancel this application?')) return
    setCancelling(true)
    setCancelError('')
    setNotice('')
    try {
      const updated = await cancelApplication(id)
      setApp(updated)
      setNotice('Application cancelled.')
      toast.success('Application cancelled', 'Your application status has been updated.')
    } catch {
      setCancelError('Could not cancel the application. Please try again.')
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
      toast.success('Document uploaded', 'The file is now attached to your application.')
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
  // Only one active appointment request may exist per application; a rejected
  // date does not block choosing another one.
  const activeAppointment = appointments.find(
    (a) => a.status === 'pending_confirmation' || a.status === 'confirmed'
  )
  const lastRejectedAppointment = appointments.find((a) => a.status === 'rejected')
  const canChooseVisitDate = app.status === 'approved' && !activeAppointment && !appointments.some((a) => a.status === 'no_show')
  const nextStep = app.status === 'approved' && activeAppointment?.status === 'confirmed'
    ? `Your visit is confirmed for ${formatDate(activeAppointment.requested_date)}. Follow the onsite instructions below and staff guidance for physical handover.`
    : app.status === 'approved' && activeAppointment?.status === 'pending_confirmation'
      ? 'Your visit request is waiting for staff review. You will be notified when the date is confirmed or rejected.'
      : NEXT_STEPS[app.status] || 'Please check with staff for the next step.'

  return (
    <div className="mx-auto max-w-4xl">
      <Link to="/applications" className="text-primary-600 text-sm font-medium hover:underline">
        ← Back to applications
      </Link>

      <div className="panel mt-5 p-5 sm:p-8">
        <p className="section-label mb-3">Your adoption journey</p>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-3xl font-bold text-primary-900">Application status</h1>
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(app.status)}`}>
            {capitalize(app.status)}
          </span>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 pb-6"><Link to={`/pets/${app.pet}`} className="text-sm font-semibold text-primary-700">For {app.pet_name} →</Link><p className="text-xs text-stone-500">Last updated {formatDate(app.updated_at)}</p></div>
        <section className="mt-6 rounded-lg bg-primary-50 p-5"><h2 className="text-sm font-bold text-primary-900">What's next</h2><p className="mt-2 text-sm leading-7 text-stone-700">{nextStep}</p></section>

        {cancelError && <Alert type="error">{cancelError}</Alert>}
        {notice && (
          <div className="mt-4">
            <Alert type="success">{notice}</Alert>
          </div>
        )}

        {app.status === 'rejected' && app.rejection_reason && (
          <div className="mt-4">
            <Alert type="error">
              <strong>Staff feedback:</strong> {app.rejection_reason}
            </Alert>
          </div>
        )}

        {DOCUMENTS_REQUESTED.includes(app.status) && <section className="mt-5 rounded-lg border border-stone-200 p-5"><h2 className="text-sm font-bold text-stone-900">Staff feedback</h2><p className="mt-2 whitespace-pre-line text-sm leading-7 text-stone-600">{feedback || (feedbackUnavailable ? 'Feedback could not be loaded. Please check your notifications.' : 'Check your notifications for the details requested by staff.')}</p><Link to="/notifications" className="mt-3 inline-block text-sm font-semibold text-primary-700">View notifications →</Link></section>}

        {app.status === 'approved' && (
          <div className="mt-6 rounded-md border border-primary-200 bg-primary-50 p-4">
            <h3 className="text-sm font-semibold text-primary-900">Onsite visit appointment</h3>

            {activeAppointment && (
              <div className="mt-2 space-y-2">
                <p className="text-sm text-stone-700">
                  Requested date:{' '}
                  <span className="font-medium">{formatDate(activeAppointment.requested_date)}</span>
                </p>
                <span
                  aria-label={`Appointment status: ${capitalize(activeAppointment.status)}`}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full ${getStatusColor(
                    activeAppointment.status
                  )}`}
                >
                  <span aria-hidden="true">
                    {activeAppointment.status === 'confirmed' ? '✓' : ''}
                  </span>
                  {capitalize(activeAppointment.status)}
                </span>
                <p className="text-sm text-stone-600">
                  {activeAppointment.status === 'pending_confirmation'
                    ? 'Waiting for staff to confirm this date. You will be notified once it has been reviewed.'
                    : 'Confirmed — you may walk in on this date between 8:00 AM and 5:00 PM for your onsite visit.'}
                </p>

                {/* Onsite visit guidance, shown only for a confirmed date.
                    These items are brought in person; they are not additional
                    online upload requirements. */}
                {activeAppointment.status === 'confirmed' && (
                  <div className="mt-3 rounded-md border border-green-200 bg-green-50 p-4">
                    <h4 className="text-sm font-semibold text-primary-900">What to Prepare for Your Visit</h4>
                    <p className="mt-1 text-sm text-stone-600">
                      Please prepare or bring the following for your visit to {app.pet_name}:
                    </p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-stone-600">
                      {VISIT_PREPARATION_ITEMS.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <p className="mt-3 text-xs text-stone-500">Center Hours: {CENTER_HOURS_TEXT}</p>
                  </div>
                )}
              </div>
            )}

            {!activeAppointment && lastRejectedAppointment && (
              <div className="mt-3">
                <Alert type="error">
                  <strong>
                    Requested date not confirmed ({formatDate(lastRejectedAppointment.requested_date)}):
                  </strong>{' '}
                  {lastRejectedAppointment.rejection_reason || 'No reason provided.'}
                </Alert>
                <p className="mt-2 text-sm text-stone-600">
                  Your adoption application is still approved — choose another visit date below.
                </p>
              </div>
            )}

            {canChooseVisitDate && (
              <form onSubmit={handleRequestAppointment} className="mt-3 space-y-3">
                <div>
                  <label htmlFor="visitDate" className="field-label mb-1">
                    Choose appointment date
                  </label>
                  <input
                    id="visitDate"
                    type="date"
                    min={todayISO()}
                    value={visitDate}
                    onChange={(e) => {
                      setVisitDate(e.target.value)
                      setApptError('')
                    }}
                    aria-describedby="visitDateHint"
                    aria-invalid={apptError ? true : undefined}
                    className="field-input sm:w-64"
                  />
                  <p id="visitDateHint" className="mt-1 text-xs text-stone-500">
                    Visits are available {CENTER_SCHEDULE_TEXT}. Weekends and past dates cannot be
                    selected, and the center is closed on holidays and work suspensions.
                  </p>
                </div>
                <FieldError message={apptError} />
                <button
                  type="submit"
                  disabled={!visitDate || apptSubmitting}
                  className="btn btn-primary"
                >
                  {apptSubmitting ? 'Submitting...' : 'Submit appointment request'}
                </button>
              </form>
            )}

            {appointments.length > 0 && (
              <ul className="mt-4 space-y-1 border-t border-primary-200 pt-3 text-xs text-stone-600">
                {appointments.map((appointment) => (
                  <li key={appointment.id}>
                    {formatDate(appointment.requested_date)} — {capitalize(appointment.status)}
                    {appointment.status === 'rejected' && appointment.rejection_reason
                      ? `: ${appointment.rejection_reason}`
                      : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {app.status === 'approved' && <AppointmentReschedulePanel
          key={app.id} applicationId={app.id} applicationStatus={app.status} appointments={appointments}
          onUpdated={async () => { if (id) setAppointments(await fetchAppointments(id) as Appointment[]) }}
        />}

        {DOCUMENTS_REQUESTED.includes(app.status) && (
          <div className="mt-6 rounded-md border border-primary-200 bg-primary-50 p-4">
            <h3 className="text-sm font-semibold text-primary-900">Add a requested document</h3>
            <p className="mt-1 text-xs text-stone-600">
              Staff asked for more information on this application. Uploads here are attached to it directly.
            </p>
            <form onSubmit={handleExtraUpload} className="mt-3 space-y-3">
              <div>
                <label htmlFor="extraType" className="field-label mb-1">
                  Document type
                </label>
                <select
                  id="extraType"
                  value={extraType}
                  onChange={(e) => setExtraType(e.target.value)}
                  className="field-input"
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
                <label htmlFor="extraFile" className="field-label mb-1">
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
                  className="w-full text-sm text-stone-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-primary-100 file:text-primary-700 hover:file:bg-primary-200"
                />
                <p className="text-xs text-stone-500 mt-1">Accepted: PDF, images, DOC/DOCX, TXT. Max 10MB.</p>
              </div>
              <FieldError message={uploadError} />
              <button
                type="submit"
                disabled={!extraFile || uploading}
                className="btn btn-primary"
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
              className="btn btn-secondary"
            >
              {cancelling ? 'Cancelling...' : 'Cancel application'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

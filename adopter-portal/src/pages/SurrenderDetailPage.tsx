import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Alert, ErrorState, Spinner } from '../components/UI'
import RequestDetails from '../features/surrenders/RequestDetails'
import RequestForm from '../features/surrenders/RequestForm'
import { surrenderError, surrenderService } from '../features/surrenders/service'
import type { SurrenderRequest } from '../features/surrenders/types'
import { isClosed, statusLabel } from '../features/surrenders/types'

export default function SurrenderDetailPage() {
  const { id } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()
  const justSubmitted = Boolean((state as { submitted?: boolean } | null)?.submitted)
  const [request, setRequest] = useState<SurrenderRequest | null>(null)
  const [failed, setFailed] = useState(false)
  const [retry, setRetry] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (justSubmitted) navigate(`/surrenders/${id}`, { replace: true, state: null })
  }, [id, justSubmitted, navigate])
  useEffect(() => {
    let active = true
    setRequest(null); setFailed(false)
    setSuccess(justSubmitted ? 'Your surrender request was submitted for review.' : '')
    setError(''); setConfirmCancel(false)
    if (id) surrenderService.get(id).then(data => { if (active) setRequest(data) }).catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [id, retry])
  if (failed) return <ErrorState message="Request unavailable. It may not belong to your account." onRetry={() => setRetry(value => value + 1)} />
  if (!request) return <Spinner />
  return <div className="mx-auto max-w-4xl space-y-6">
    <Link to="/surrenders" className="text-sm font-semibold text-primary-700">← My Surrender Requests</Link>
    <div><h1 className="text-3xl font-bold text-stone-900">Surrender request for {request.pet_name}</h1><p className="mt-2 font-semibold text-primary-700">{statusLabel(request.status)}</p></div>
    {success && <Alert type="success">{success}</Alert>}
    {error && <Alert type="error">{error}</Alert>}
    {request.status === 'received' ? <Alert>The center has received your pet. Your request is complete.</Alert> : !isClosed(request.status) && <Alert>Keep the pet in your care. Submitting or scheduling a request does not guarantee acceptance or transfer custody.</Alert>}
    <RequestDetails request={request} />
    {request.status === 'needs_information' && <section aria-label="Update requested information"><h2 className="mb-3 text-xl font-bold text-stone-900">Additional information requested</h2><RequestForm key={request.updated_at} initial={request} onSaved={data => { setRequest(data); setSuccess('Updated information sent for staff review.') }} /></section>}
    {!isClosed(request.status) && <section className="panel p-5" aria-label="Cancel surrender request"><h2 className="font-bold text-stone-900">Need to withdraw your request?</h2>{confirmCancel ? <div className="mt-3 space-y-3"><p className="text-sm text-stone-600">This closes your request and cancels its intake schedule. The pet remains in your care.</p><div className="flex flex-wrap gap-3"><button className="btn btn-danger" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { setRequest(await surrenderService.action(request.id, 'cancel')); setSuccess('Your request was cancelled.'); setConfirmCancel(false) } catch (err) { setError(surrenderError(err)) } finally { setBusy(false) } }}>{busy ? 'Cancelling…' : 'Confirm cancellation'}</button><button className="btn btn-outline" disabled={busy} onClick={() => setConfirmCancel(false)}>Keep request</button></div></div> : <button className="btn btn-outline mt-3" onClick={() => setConfirmCancel(true)}>Cancel request</button>}</section>}
  </div>
}

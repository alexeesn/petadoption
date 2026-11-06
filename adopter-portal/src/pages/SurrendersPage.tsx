import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, Spinner } from '../components/UI'
import { surrenderService } from '../features/surrenders/service'
import type { SurrenderPage } from '../features/surrenders/types'
import { dateLabel, statusLabel, surrenderStatuses } from '../features/surrenders/types'

export default function SurrendersPage() {
  const [result, setResult] = useState<SurrenderPage | null>(null)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    setResult(null); setError(false)
    surrenderService.list(page, status).then(data => { if (active) setResult(data) }).catch(() => { if (active) setError(true) })
    return () => { active = false }
  }, [page, status, retry])
  return <div className="mx-auto max-w-4xl space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold text-stone-900">My Surrender Requests</h1><p className="mt-2 text-sm text-stone-600">Request help from the center and track the intake process.</p></div><Link to="/surrenders/new" className="btn btn-primary">Request to surrender a pet</Link></div>
    <p className="rounded-lg border border-stone-200 p-4 text-sm text-stone-600">The center reviews each request based on the pet’s needs and available space. Keep the pet in your care until the center confirms physical handover.</p>
    <div className="max-w-xs"><label htmlFor="surrender-status-filter" className="field-label">Request status</label><select id="surrender-status-filter" className="field-input" value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="">All statuses</option>{surrenderStatuses.map(value => <option key={value} value={value}>{statusLabel(value)}</option>)}</select></div>
    {error ? <ErrorState message="Could not load your surrender requests." onRetry={() => setRetry(value => value + 1)} /> : !result ? <Spinner /> : !result.results.length ? <EmptyState message="No surrender requests match this view." /> : <>
      <div className="space-y-3">{result.results.map(request => <Link key={request.id} to={`/surrenders/${request.id}`} className="panel block p-5 hover:border-primary-400"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-bold text-stone-900">{request.pet_name}</h2><span className="rounded-md bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-700">{statusLabel(request.status)}</span></div><p className="mt-2 text-sm text-stone-600">{statusLabel(request.species)} · Submitted {new Date(request.created_at).toLocaleDateString()}</p>{request.intake_date && <p className="mt-2 text-sm font-semibold text-primary-700">Intake: {dateLabel(request.intake_date)}</p>}<span className="mt-3 block text-sm font-semibold text-primary-700">View request →</span></Link>)}</div>
      <nav aria-label="Surrender request pages" className="flex items-center justify-between gap-3"><button className="btn btn-outline" disabled={!result.previous} onClick={() => setPage(value => value - 1)}>Previous</button><p className="text-sm text-stone-600">Page {page} · {result.count} requests</p><button className="btn btn-outline" disabled={!result.next} onClick={() => setPage(value => value + 1)}>Next</button></nav>
    </>}
  </div>
}

import { useEffect, useState } from 'react'
import { surrenderService } from './service'
import type { SurrenderRequest } from './types'
import { dateLabel, statusLabel } from './types'

function PrivatePhoto({ requestId, photoId, petName }: { requestId: string; photoId: string; petName: string }) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let disposed = false
    let objectUrl = ''
    surrenderService.photo(requestId, photoId).then(blob => {
      if (disposed) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => { if (!disposed) setFailed(true) })
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [requestId, photoId])
  if (failed) return <p role="status" className="p-4 text-sm text-stone-600">Pet photo unavailable.</p>
  if (!url) return <p role="status" className="p-4 text-sm text-stone-500">Loading photo…</p>
  return <a href={url} target="_blank" rel="noreferrer" aria-label={`Open full photo of ${petName}`}><img src={url} alt={`${petName}, submitted by the owner`} className="h-44 w-full rounded-lg object-cover" /></a>
}

export default function RequestDetails({ request }: { request: SurrenderRequest }) {
  return <div className="space-y-6">
    <section className="panel p-5 sm:p-6" aria-label="Pet and owner information">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{request.photos.map(photo => <PrivatePhoto key={photo.id} requestId={request.id} photoId={photo.id} petName={request.pet_name} />)}</div>
      <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
        {[['Species', statusLabel(request.species)], ['Breed', request.breed || 'Not specified'], ['Estimated age', `${request.age_years} years, ${request.age_months} months`], ['Sex', statusLabel(request.gender)], ['Contact number', request.contact_number]].map(([label, value]) => <div key={label}><dt className="font-semibold text-stone-500">{label}</dt><dd className="mt-1 text-stone-900">{value}</dd></div>)}
      </dl>
      {[['Reason for surrender', request.reason], ['Health and vaccination information (owner-reported)', request.health_information], ['Behavior information (owner-reported)', request.behavior_information]].map(([label, value]) => <div key={label} className="mt-5"><h2 className="text-sm font-semibold text-stone-800">{label}</h2><p className="mt-1 whitespace-pre-wrap break-words text-sm text-stone-600">{value}</p></div>)}
    </section>
    {request.intake_date && request.status === 'intake_scheduled' && <section className="panel border-primary-200 p-5" aria-label="Intake schedule"><h2 className="font-bold text-stone-900">Intake scheduled: {dateLabel(request.intake_date)}</h2><p className="mt-2 whitespace-pre-wrap break-words text-sm text-stone-700">{request.intake_instructions}</p><p className="mt-3 text-sm text-stone-600">Scheduling is not final acceptance. Keep the pet in your care until the center receives it and confirms the handover.</p></section>}
    <section className="panel p-5 sm:p-6" aria-label="Request history"><h2 className="text-lg font-bold text-stone-900">Request history</h2><ol className="mt-4 space-y-4">{request.history.map(event => <li key={event.id} className="border-l-2 border-stone-200 pl-4"><p className="text-sm font-semibold text-stone-900">{statusLabel(event.new_status)} <span className="font-normal text-stone-500">· {new Date(event.created_at).toLocaleString()}</span></p>{event.intake_date && <p className="mt-1 text-sm text-stone-600">Intake date: {dateLabel(event.intake_date)}</p>}<p className="mt-1 whitespace-pre-wrap break-words text-sm text-stone-700">{event.note}</p></li>)}</ol></section>
  </div>
}

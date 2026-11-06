import { FormEvent, useState } from 'react'
import { surrenderError, surrenderService } from './service'
import type { SurrenderRequest } from './types'

export default function RequestForm({ initial, onSaved }: { initial?: SurrenderRequest; onSaved: (request: SurrenderRequest) => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const required = ['pet_name', 'reason', 'health_information', 'behavior_information', 'contact_number']
    if (required.some(name => !String(data.get(name) || '').trim())) { setError('Complete all required fields. Enter “Unknown” for health or behavior information you do not know.'); return }
    const files = data.getAll('photos').filter((file): file is File => file instanceof File && file.size > 0)
    const contact = String(data.get('contact_number') || '')
    const digits = contact.replace(/\D/g, '')
    if (!/^[+()0-9 .-]+$/.test(contact) || digits.length < 7 || digits.length > 15) { setError('Enter a valid contact number with 7 to 15 digits.'); return }
    if ((!initial && !files.length) || files.length > 5 || (initial?.photos.length || 0) + files.length > 10 || files.some(file => file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png'].includes(file.type))) { setError('Upload up to 5 JPEG or PNG pet photos, up to 5 MB each (10 photos total per request). At least one photo is required for a new request.'); return }
    data.delete('photos')
    files.forEach(file => data.append('photos', file))
    data.set('ownership_confirmed', 'true')
    setBusy(true)
    setError('')
    try { onSaved(initial ? await surrenderService.resubmit(initial.id, data) : await surrenderService.create(data)) }
    catch (err) { setError(surrenderError(err)) }
    finally { setBusy(false) }
  }
  return <form onSubmit={submit} className="panel p-5 sm:p-7" aria-describedby={error ? 'surrender-form-error' : 'surrender-form-help'}>
    <p id="surrender-form-help" className="mb-6 text-sm text-stone-600">Tell us about the pet so the center can assess the request and its available space. For details you do not know, enter “Unknown.”</p>
    <fieldset disabled={busy} className="space-y-5">
      <legend className="sr-only">Pet surrender details</legend>
      <div className="grid gap-5 sm:grid-cols-2">
        <label className="block"><span className="field-label">Pet name</span><input name="pet_name" required maxLength={150} defaultValue={initial?.pet_name} className="field-input" /></label>
        <div><label htmlFor="surrender-species" className="field-label">Species</label><select id="surrender-species" name="species" defaultValue={initial?.species || 'dog'} className="field-input"><option value="dog">Dog</option><option value="cat">Cat</option><option value="other">Other</option></select></div>
        <label className="block"><span className="field-label">Breed (optional)</span><input name="breed" maxLength={150} defaultValue={initial?.breed} className="field-input" /></label>
        <div><label htmlFor="surrender-sex" className="field-label">Sex</label><select id="surrender-sex" name="gender" defaultValue={initial?.gender || 'unknown'} className="field-input"><option value="unknown">Unknown</option><option value="male">Male</option><option value="female">Female</option></select></div>
        <label className="block"><span className="field-label">Estimated age — years</span><input name="age_years" type="number" min={0} max={40} required defaultValue={initial?.age_years ?? 0} className="field-input" /></label>
        <label className="block"><span className="field-label">Estimated age — months</span><input name="age_months" type="number" min={0} max={11} required defaultValue={initial?.age_months ?? 0} className="field-input" /></label>
      </div>
      {[['reason', 'Reason for surrender'], ['health_information', 'Known health conditions and vaccination information'], ['behavior_information', 'Behavior and temperament']].map(([name, label]) => <div key={name}><label htmlFor={`surrender-${name}`} className="field-label">{label}</label><textarea id={`surrender-${name}`} name={name} rows={3} required maxLength={5000} defaultValue={initial ? initial[name as 'reason' | 'health_information' | 'behavior_information'] : ''} className="field-input" /></div>)}
      <label className="block"><span className="field-label">Contact number</span><input name="contact_number" type="tel" required maxLength={30} defaultValue={initial?.contact_number} className="field-input" /></label>
      <div><label htmlFor="surrender-photos" className="field-label">{initial ? 'Additional pet photos (optional)' : 'Pet photos (1 to 5)'}</label><input id="surrender-photos" name="photos" type="file" accept="image/jpeg,image/png" multiple required={!initial} className="field-input" aria-describedby="surrender-photo-help" /><p id="surrender-photo-help" className="mt-1 text-xs text-stone-500">JPEG or PNG, up to 5 MB each. Photos are private to your request and center staff.{initial && ` Existing photos are kept. Add up to ${Math.min(5, 10 - initial.photos.length)} more.`}</p></div>
      <label className="flex items-start gap-3 text-sm text-stone-700"><input name="ownership_confirmed" type="checkbox" required className="mt-1" /><span>I own this pet or am authorized to surrender it. I understand that submitting a request does not transfer custody or guarantee acceptance.</span></label>
      {error && <p id="surrender-form-error" role="alert" className="text-sm text-red-700">{error}</p>}
      <button type="submit" disabled={busy} className="btn btn-primary">{busy ? 'Submitting…' : initial ? 'Send updated information' : 'Submit surrender request'}</button>
    </fieldset>
  </form>
}

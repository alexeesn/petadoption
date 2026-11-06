import { FormEvent, useEffect, useId, useRef, useState } from 'react';
import { Button, Loading, StatusBadge } from '../../components/UI';
import { useAuth } from '../../context/AuthContext';
import { petService } from '../../services/apiService';
import type { Pet } from '../../types';
import { apiError } from '../../utils/apiError';
import { formatDate, formatDateTime, philippineDate } from '../../utils/format';

export default function PetDeathDialog({ petId, onSaved, onClose }: { petId: string; onSaved: (pet: Pet) => void; onClose: () => void }) {
  const { user } = useAuth();
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [pet, setPet] = useState<Pet | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [correcting, setCorrecting] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let active = true;
    setError('');
    petService.retrieve(petId).then(({ data }) => { if (active) setPet(data as Pet); }).catch(() => { if (active) setError('Could not load the pet record.'); });
    return () => { active = false; };
  }, [petId, retry]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pet || busy) return;
    const data = new FormData(event.currentTarget);
    const reason = String(data.get('reason') || '').trim();
    if (correcting && !reason) { setError('A correction reason is required.'); return; }
    setBusy(true); setError('');
    try {
      const response = correcting ? await petService.correctDeath(pet.id, reason) : await petService.recordDeath(pet.id, {
        death_date: data.get('death_date'), cause: String(data.get('cause') || '').trim() || 'Unknown',
        veterinarian: String(data.get('veterinarian') || '').trim(), internal_notes: String(data.get('internal_notes') || '').trim(), confirmed: true,
      });
      onSaved(response.data);
      onClose();
    } catch (err) { setError(apiError(err, 'Could not save this pet record.')); }
    finally { setBusy(false); }
  }

  return <dialog ref={dialog} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} className="max-h-[90dvh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-xl border-0 bg-white p-5 shadow-xl backdrop:bg-black/50 sm:p-7">
    <div className="flex items-start justify-between gap-3"><h2 id={titleId} className="text-xl font-bold text-stone-900">{pet?.status === 'deceased' ? 'Pet death record' : 'Record pet death'}</h2><Button variant="outline" onClick={onClose} disabled={busy}>Close</Button></div>
    {!pet && !error && <Loading />}
    {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    {!pet && error && <Button className="mt-3" onClick={() => setRetry(value => value + 1)}>Try again</Button>}
    {pet && <div className="mt-5 space-y-5">
      <div className="flex flex-wrap items-center gap-3"><h3 className="text-lg font-semibold text-stone-900">{pet.name}</h3><StatusBadge status={pet.status} /></div>
      {(pet.death_records || []).map(record => <section key={record.id} className="space-y-2 rounded-lg border border-stone-200 p-4 text-sm text-stone-700" aria-label="Saved death entry"><p className="font-semibold text-stone-900">Date of death: {formatDate(record.death_date)}</p><p className="whitespace-pre-wrap break-words">Cause: {record.cause}</p>{record.veterinarian && <p>Veterinarian: {record.veterinarian}</p>}{record.internal_notes && <p className="whitespace-pre-wrap break-words">Internal notes: {record.internal_notes}</p>}<p className="break-words text-xs text-stone-500">Recorded by {record.recorded_by_email} · {formatDateTime(record.recorded_at)}</p>{record.corrected_at && <div className="border-t border-stone-200 pt-2"><p className="font-semibold">Entry corrected — original details retained</p><p className="whitespace-pre-wrap break-words">{record.correction_reason}</p><p className="mt-1 break-words text-xs text-stone-500">{record.corrected_by_email} · {formatDateTime(record.corrected_at)}</p></div>}</section>)}
      {pet.status === 'deceased' && !correcting && <><p className="text-sm text-stone-600">This pet is excluded from public listings. Death details are visible only to staff and administrators.</p>{user?.role === 'admin' && <Button variant="outline" onClick={() => setCorrecting(true)}>Correct mistaken entry</Button>}</>}
      {((pet.status !== 'deceased' && pet.status !== 'adopted') || correcting) && <form onSubmit={submit} className="space-y-4" aria-label={correcting ? 'Correct death entry' : 'Record death details'}>
        <fieldset disabled={busy} className="space-y-4">
          <legend className="sr-only">{correcting ? 'Correction details' : 'Death details'}</legend>
          {correcting ? <><p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-stone-800">The original entry stays in history. The pet returns to For Assessment. Cancelled applications and visits stay closed; payment reviews remain pending.</p><label htmlFor="death-correction-reason" className="field-label">Reason for correction</label><textarea id="death-correction-reason" name="reason" required maxLength={2000} rows={3} className="field-input" /></> : <>
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-stone-800">This removes the pet from public listings, cancels active applications and visits, and flags applicable payments for review. Medical records and receipts are retained. No automatic refund is issued.</p>
            <label className="block"><span className="field-label">Date of death</span><input name="death_date" type="date" required max={philippineDate()} min={pet.arrival_date || undefined} defaultValue={philippineDate()} className="field-input" /></label>
            <label className="block"><span className="field-label">Cause of death (enter Unknown if unconfirmed)</span><input name="cause" maxLength={1000} defaultValue="Unknown" className="field-input" /></label>
            <label className="block"><span className="field-label">Veterinarian (optional)</span><input name="veterinarian" maxLength={200} className="field-input" /></label>
            <div><label htmlFor="pet-death-internal-notes" className="field-label">Internal notes (staff only)</label><textarea id="pet-death-internal-notes" name="internal_notes" rows={3} maxLength={5000} className="field-input" /></div>
          </>}
          <label className="flex items-start gap-3 text-sm text-stone-700"><input type="checkbox" required className="mt-1" /><span>{correcting ? 'I confirm this was an incorrect death entry and authorize the recorded correction.' : 'I confirm this pet died while in the center’s custody and understand the effects on its adoption activities.'}</span></label>
          <div className="flex flex-wrap justify-end gap-3">{correcting && <Button variant="outline" onClick={() => setCorrecting(false)}>Keep original entry</Button>}<Button type="submit" variant={correcting ? 'primary' : 'danger'} disabled={busy}>{busy ? 'Saving…' : correcting ? 'Confirm correction' : 'Record death and close adoption activities'}</Button></div>
        </fieldset>
      </form>}
    </div>}
  </dialog>;
}

import { FormEvent, useState } from 'react';
import { Button } from '../../components/UI';
import { DecisionDialog } from '../../components/DecisionDialog';
import { surrenderService } from './service';
import type { SurrenderRequest } from './types';

export default function ReviewForm({ request, onSaved }: { request: SurrenderRequest; onSaved: (value: SurrenderRequest) => void }) {
  const [target, setTarget] = useState('');
  const [pending, setPending] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState('');
  const canAsk = ['submitted', 'waitlisted', 'intake_scheduled'].includes(request.status);
  const canWaitlist = ['submitted', 'needs_information', 'intake_scheduled'].includes(request.status);
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const note = String(data.get('note') || '').trim();
    const instructions = String(data.get('intake_instructions') || '').trim();
    if (!note || (target === 'intake_scheduled' && !instructions)) { setValidation('Complete the message and intake instructions before continuing.'); return; }
    setValidation('');
    setPending({ status: target, note, internal_notes: String(data.get('internal_notes') || '').trim(), ...(target === 'intake_scheduled' ? { intake_date: data.get('intake_date'), intake_instructions: instructions } : {}) });
  }
  return <section className="panel p-5 sm:p-6" aria-label="Staff review">
    <h2 className="text-lg font-bold text-stone-900">Review and scheduling</h2>
    <p className="mt-2 text-sm text-stone-600">Check the pet’s needs and center capacity. Scheduling does not confirm acceptance.</p>
    <form onSubmit={submit} className="mt-5 space-y-4">
      <div><label htmlFor="surrender-decision" className="field-label">Decision</label><select id="surrender-decision" required value={target} onChange={event => setTarget(event.target.value)} className="field-input"><option value="">Choose a decision</option>{canAsk && <option value="needs_information">Request additional information</option>}{canWaitlist && <option value="waitlisted">Waitlist — awaiting capacity</option>}<option value="intake_scheduled">{request.status === 'intake_scheduled' ? 'Reschedule intake / update instructions' : 'Schedule intake'}</option><option value="declined">Decline request</option></select></div>
      {target === 'intake_scheduled' && <div className="space-y-4"><label className="block"><span className="field-label">Intake date</span><input type="date" name="intake_date" min={today} required defaultValue={request.intake_date || ''} className="field-input" /></label><div><label htmlFor="surrender-intake-instructions" className="field-label">Center location, time, and intake requirements</label><textarea id="surrender-intake-instructions" name="intake_instructions" rows={3} required maxLength={2000} defaultValue={request.intake_instructions} className="field-input" /></div></div>}
      <div><label htmlFor="surrender-owner-note" className="field-label">Message to owner / reason for decision</label><textarea id="surrender-owner-note" name="note" rows={3} required maxLength={2000} className="field-input" /></div>
      <div><label htmlFor="surrender-internal-note" className="field-label">Internal notes (staff only)</label><textarea id="surrender-internal-note" name="internal_notes" rows={3} maxLength={5000} className="field-input" /></div>
      {validation && <p role="alert" className="text-sm text-red-700">{validation}</p>}
      <Button type="submit" disabled={!target}>Review decision</Button>
    </form>
    {pending && <DecisionDialog title="Save surrender decision" requireReason={false} description={`The request will become ${String(pending.status).replace(/_/g, ' ')}. The owner will receive your message and scheduling instructions, when applicable.`} onClose={() => setPending(null)} onConfirm={async () => onSaved(await surrenderService.action(request.id, 'review', pending))} />}
  </section>;
}

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button, ErrorMessage, Loading, Select, StatusBadge } from '../components/UI';
import { DecisionDialog } from '../components/DecisionDialog';
import RequestDetails from '../features/surrenders/RequestDetails';
import ReviewForm from '../features/surrenders/ReviewForm';
import { surrenderService } from '../features/surrenders/service';
import type { SurrenderRequest } from '../features/surrenders/types';
import { isClosed } from '../features/surrenders/types';

export default function SurrenderDetailPage() {
  const { id } = useParams();
  const [request, setRequest] = useState<SurrenderRequest | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [success, setSuccess] = useState('');
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [petStatus, setPetStatus] = useState('for_assessment');
  useEffect(() => {
    let active = true;
    setRequest(null); setFailed(false);
    if (id) surrenderService.get(id).then(data => { if (active) setRequest(data); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [id, retry]);
  if (failed) return <><ErrorMessage message="Request unavailable." /><Button onClick={() => setRetry(value => value + 1)}>Try again</Button></>;
  if (!request) return <Loading />;
  return <div className="mx-auto max-w-6xl space-y-6">
    <Link to="/surrenders" className="text-sm font-semibold text-primary-700">← Surrender Requests</Link>
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold text-stone-900">{request.pet_name} — surrender request</h1><p className="mt-2 text-sm text-stone-600">Owner: {request.owner_name || request.owner_email}</p><p className="mt-1 break-all text-sm text-stone-500">{request.owner_email}</p></div><StatusBadge status={request.status} /></div>
    {success && <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-900">{success}</p>}
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]"><RequestDetails request={request} /><div className="space-y-6">
      {!isClosed(request.status) && <ReviewForm key={request.updated_at} request={request} onSaved={data => { setRequest(data); setSuccess('Decision saved and owner notified.'); }} />}
      {request.status === 'intake_scheduled' && <section className="panel p-5 sm:p-6" aria-label="Physical intake"><h2 className="text-lg font-bold text-stone-900">Confirm physical intake</h2><p className="mt-2 text-sm text-stone-600">Use after the pet arrives and ownership authorization, consent, and the physical handover have been checked. Owner-reported health details remain separate from official medical records.</p><div className="mt-5"><Select label="Initial official pet status" value={petStatus} onChange={event => setPetStatus(event.target.value)} options={[{ value: 'for_assessment', label: 'For assessment' }, { value: 'under_medical_care', label: 'Under medical care' }, { value: 'available', label: 'Available — assessed and ready for adoption' }, { value: 'inactive', label: 'Inactive' }]} /></div><Button className="mt-4" onClick={() => setIntakeOpen(true)}>Confirm intake</Button></section>}
      {request.pet && <section className="panel p-5"><h2 className="font-bold text-stone-900">Official pet record created</h2><p className="mt-2 break-all text-xs text-stone-500">Pet reference: {request.pet}</p><p className="mt-3 text-sm text-stone-600">Review the pet’s official information, add listing photos, and complete any medical assessment in Pet Management. Request photos remain private.</p><Link to={`/pets?pet=${request.pet}`} className="btn btn-primary mt-4">Manage official pet record</Link></section>}
      <section className="panel p-5" aria-label="Internal review history"><h2 className="font-bold text-stone-900">Internal review history</h2><p className="mt-1 text-xs text-stone-500">Visible only to staff and administrators.</p>{request.history.filter(event => event.internal_notes).length ? request.history.filter(event => event.internal_notes).map(event => <div key={event.id} className="mt-4 border-t border-stone-200 pt-3"><p className="text-xs text-stone-500">{event.actor_email} · {new Date(event.created_at).toLocaleString()}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm text-stone-700">{event.internal_notes}</p></div>) : <p className="mt-3 text-sm text-stone-500">No internal notes yet.</p>}</section>
    </div></div>
    {intakeOpen && <DecisionDialog title="Confirm pet received" requireReason={false} description="This confirms transfer into the center’s custody and creates one official pet record. This request can no longer be cancelled or edited by the owner." confirmationLabel="I confirm the center physically received this pet and verified the owner’s authorization and handover consent." onClose={() => setIntakeOpen(false)} onConfirm={async () => { setRequest(await surrenderService.action(request.id, 'confirm-intake', { confirmed: true, pet_status: petStatus })); setSuccess('Physical intake confirmed. The official pet record has been created.'); }} />}
  </div>;
}

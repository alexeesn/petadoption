import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Loading, ErrorMessage, Button } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { applicationService } from '../services/apiService';
import type { Application } from '../types';

const VALID_STATUS_TRANSITIONS: Record<string, string[]> = {
  submitted: ['under_review', 'rejected'],
  under_review: ['pending_documents', 'additional_info_requested', 'approved', 'rejected'],
  pending_documents: ['under_review', 'rejected'],
  additional_info_requested: ['under_review', 'rejected'],
};

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [app, setApp] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    applicationService
      .retrieve(id)
      .then((res) => {
        setApp(res.data);
        setNotes(res.data.staff_notes || '');
        setRejectionReason(res.data.rejection_reason || '');
      })
      .catch(() => setError('Failed to load application.'))
      .finally(() => setLoading(false));
  }, [id]);

  const transition = (newStatus: string) => {
    if (!app) return;
    setUpdating(true);
    applicationService
      .updateStatus(app.id, {
        status: newStatus,
        staff_notes: notes,
        rejection_reason: newStatus === 'rejected' ? rejectionReason : '',
      })
      .then((res) => {
        setApp(res.data);
        setNotes(res.data.staff_notes || '');
      })
      .catch((e) => setError(e.response?.data?.error || 'Failed to update status.'))
      .finally(() => setUpdating(false));
  };

  if (loading) return <Loading label="Loading application..." />;
  if (error) return <ErrorMessage message={error} />;
  if (!app) return null;

  const allowed = VALID_STATUS_TRANSITIONS[app.status] || [];

  return (
    <div>
      <PageHeader title="Application Details" subtitle={app.pet_name} />
      <Card className="p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-slate-900 mb-2">Pet</h3>
            <p className="text-slate-600">{app.pet_name}</p>
            <h3 className="font-semibold text-slate-900 mt-4 mb-2">Adopter</h3>
            <p className="text-slate-600">{app.adopter_email}</p>
            <h3 className="font-semibold text-slate-900 mt-4 mb-2">Status</h3>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800`}>
              {app.status.replace(/_/g, ' ')}
            </span>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 mb-2">Why adopt?</h3>
            <p className="text-slate-600 whitespace-pre-wrap">{app.why_adopt}</p>
            <h3 className="font-semibold text-slate-900 mt-4 mb-2">Experience with pets</h3>
            <p className="text-slate-600 whitespace-pre-wrap">{app.experience_with_pets}</p>
          </div>
        </div>
      </Card>

      <Card className="p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-slate-900 mb-2">Living situation</h3>
            <p className="text-slate-600 whitespace-pre-wrap">{app.living_situation}</p>
            <h3 className="font-semibold text-slate-900 mt-4 mb-2">Other pets</h3>
            <p className="text-slate-600">{app.has_other_pets ? app.other_pets_description : 'No'}</p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 mb-2">References</h3>
            <p className="text-slate-600 whitespace-pre-wrap">{app.references}</p>
            {app.rejection_reason && (
              <>
                <h3 className="font-semibold text-red-600 mt-4 mb-2">Rejection reason</h3>
                <p className="text-slate-600 whitespace-pre-wrap">{app.rejection_reason}</p>
              </>
            )}
          </div>
        </div>
      </Card>

      <Card className="p-6 mb-6">
        <h3 className="font-semibold text-slate-900 mb-2">Internal staff notes</h3>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Internal notes (not visible to adopter)"
        />
      </Card>

      {app.status === 'rejected' && (
        <Card className="p-6 mb-6">
          <h3 className="font-semibold text-slate-900 mb-2">Rejection reason</h3>
          <textarea
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </Card>
      )}

      {allowed.length > 0 && (
        <Card className="p-6">
          <h3 className="font-semibold text-slate-900 mb-3">Update status</h3>
          <div className="flex flex-wrap gap-3">
            {allowed.includes('under_review') && (
              <Button onClick={() => transition('under_review')} disabled={updating}>Mark Under Review</Button>
            )}
            {allowed.includes('pending_documents') && (
              <Button variant="secondary" onClick={() => transition('pending_documents')} disabled={updating}>Request Documents</Button>
            )}
            {allowed.includes('additional_info_requested') && (
              <Button variant="secondary" onClick={() => transition('additional_info_requested')} disabled={updating}>Request Additional Info</Button>
            )}
            {allowed.includes('approved') && (
              <Button variant="secondary" onClick={() => transition('approved')} disabled={updating}>Approve</Button>
            )}
            {allowed.includes('rejected') && (
              <Button variant="danger" onClick={() => transition('rejected')} disabled={updating || !rejectionReason.trim()}>
                Reject
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

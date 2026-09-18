import { ReactNode, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Card, Loading, ErrorMessage, Button, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import {
  applicationService,
  openDocument,
  petService,
  saveDocument,
} from '../services/apiService';
import type { Application, Document, Pet } from '../types';
import { formatDateTime, formatFileSize } from '../utils/format';

/**
 * Mirrors Application.VALID_TRANSITIONS in
 * backend/apps/applications/models.py, so the buttons shown here are exactly
 * the transitions the API accepts.  (Previously this map claimed
 * "submitted -> rejected" was allowed while the backend refused it.)
 */
const VALID_STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ['submitted', 'cancelled'],
  submitted: ['under_review', 'pending_documents', 'approved', 'rejected', 'cancelled'],
  under_review: ['pending_documents', 'additional_info_requested', 'approved', 'rejected'],
  pending_documents: ['under_review', 'cancelled'],
  additional_info_requested: ['under_review', 'cancelled'],
};

/**
 * Documents an adopter must attach before the application can be submitted
 * (mirrors REQUIRED_DOCUMENT_TYPES in backend/apps/documents/serializers.py).
 * Used here only to show the reviewer whether each one arrived with the
 * application; the validation itself stays on the server.
 */
const REQUIRED_DOCUMENTS = [
  { type: 'identification', label: 'Valid ID' },
  { type: 'proof_of_address', label: 'Proof of Address' },
];

function humanise(value: string) {
  return value.replace(/_/g, ' ');
}

function ageLabel(months?: number) {
  if (months === undefined || months === null) return '—';
  const years = Math.floor(months / 12);
  const rest = months % 12;
  if (years > 0 && rest > 0) return `${years} yr ${rest} mo`;
  if (years > 0) return `${years} yr`;
  return `${months} mo`;
}

function Detail({ label, value }: { label: string; value?: ReactNode }) {
  const empty = value === undefined || value === null || value === ''
    || (typeof value === 'string' && value.trim() === '');
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-800 whitespace-pre-wrap">{empty ? '—' : value}</dd>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-6 mb-6">
      <h3 className="text-base font-semibold text-slate-900 mb-4">{title}</h3>
      {children}
    </Card>
  );
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [app, setApp] = useState<Application | null>(null);
  const [pet, setPet] = useState<Pet | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [notes, setNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyDocument, setBusyDocument] = useState('');
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setLoadError('');
    applicationService
      .retrieve(id)
      .then((res) => {
        setApp(res.data);
        setNotes(res.data.staff_notes || '');
        setRejectionReason(res.data.rejection_reason || '');
        // The selected pet's details (photo, description, ...) live on their
        // own endpoint; failing to load them must not break the review page.
        petService
          .retrieve(res.data.pet)
          .then((petRes) => setPet(petRes.data))
          .catch(() => setPet(null));
      })
      .catch(() => setLoadError('Failed to load this application.'))
      .finally(() => setLoading(false));
  }, [id]);

  const transition = (newStatus: string) => {
    if (!app) return;
    setBusy(true);
    setNotice('');
    setActionError('');
    applicationService
      .updateStatus(app.id, {
        status: newStatus,
        staff_notes: notes,
        rejection_reason: newStatus === 'rejected' ? rejectionReason : '',
      })
      .then((res) => {
        setApp(res.data);
        setNotes(res.data.staff_notes || '');
        setNotice(`Application set to "${humanise(res.data.status)}".`);
      })
      .catch((e) => setActionError(e.response?.data?.error || 'Failed to update status.'))
      .finally(() => setBusy(false));
  };

  const saveNotes = () => {
    if (!app) return;
    setBusy(true);
    setNotice('');
    setActionError('');
    applicationService
      .update(app.id, { staff_notes: notes })
      .then((res) => {
        setApp(res.data);
        setNotes(res.data.staff_notes || '');
        setNotice('Internal notes saved.');
      })
      .catch((e) => setActionError(e.response?.data?.error || 'Failed to save notes.'))
      .finally(() => setBusy(false));
  };

  const viewDocument = async (doc: Document) => {
    setBusyDocument(doc.id);
    setActionError('');
    try {
      // Private file: fetched with the auth token rather than a plain link.
      await openDocument(doc.id);
    } catch {
      setActionError('Could not open that document. You may need to sign in again.');
    } finally {
      setBusyDocument('');
    }
  };

  const downloadDocument = async (doc: Document) => {
    setBusyDocument(doc.id);
    setActionError('');
    try {
      await saveDocument(doc.id, doc.original_filename);
    } catch {
      setActionError('Could not download that document. You may need to sign in again.');
    } finally {
      setBusyDocument('');
    }
  };

  if (loading) return <Loading label="Loading application..." />;
  if (loadError) return <ErrorMessage message={loadError} />;
  if (!app) return null;

  const allowed = VALID_STATUS_TRANSITIONS[app.status] || [];
  const documents = app.documents ?? [];
  const uploadedTypes = new Set(documents.map((doc) => doc.document_type));
  const profile = app.adopter_profile;
  const primaryImage =
    pet?.images?.find((image) => image.is_primary) ?? pet?.images?.[0] ?? null;
  const address = profile
    ? [
        profile.address_line1,
        profile.address_line2,
        [profile.city, profile.state, profile.zip_code].filter(Boolean).join(', '),
      ]
        .filter((part) => part && part.trim() !== '')
        .join('\n')
    : '';

  return (
    <div>
      <PageHeader
        title="Application Review"
        subtitle={`${app.pet_name} — ${app.adopter_name || app.adopter_email}`}
      />
      <div className="mb-4">
        <Link to="/applications" className="text-sm text-indigo-600 hover:underline">
          &larr; Back to applications
        </Link>
      </div>

      {notice && (
        <div
          role="status"
          className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
        >
          {notice}
        </div>
      )}
      {actionError && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {actionError}
        </div>
      )}

      <SectionCard title="Review summary">
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Detail label="Status" value={<StatusBadge status={app.status} />} />
          <Detail label="Submitted" value={formatDateTime(app.created_at)} />
          <Detail label="Last updated" value={formatDateTime(app.updated_at)} />
          <Detail label="Reviewed by" value={app.reviewed_by_email} />
          <Detail
            label="Reviewed at"
            value={app.reviewed_at ? formatDateTime(app.reviewed_at) : ''}
          />
        </dl>
      </SectionCard>

      <SectionCard title="Applicant Information">
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Detail label="Name" value={app.adopter_name} />
          <Detail label="Email" value={app.adopter_email} />
          <Detail label="Phone" value={profile?.phone_number} />
          <Detail label="Date of birth" value={profile?.date_of_birth} />
          <Detail label="Address" value={address} />
          <Detail
            label="Housing type"
            value={profile?.housing_type ? humanise(profile.housing_type) : ''}
          />
          <Detail
            label="Owns or rents"
            value={profile?.owns_or_rents ? humanise(profile.owns_or_rents) : ''}
          />
          <Detail label="Has a yard" value={profile ? (profile.has_yard ? 'Yes' : 'No') : ''} />
          <Detail
            label="Household members"
            value={profile ? String(profile.household_members) : ''}
          />
        </dl>
        {profile?.other_pets && (
          <dl className="mt-4">
            <Detail label="Pets already in the home (profile)" value={profile.other_pets} />
          </dl>
        )}
        {!profile && (
          <p className="mt-4 text-sm text-slate-500">
            This adopter has not saved profile details yet, so only the account email is
            available.
          </p>
        )}
      </SectionCard>

      <SectionCard title="Pet Information">
        <div className="flex flex-col sm:flex-row gap-6">
          {primaryImage ? (
            <img
              src={primaryImage.image}
              alt={`Photo of ${app.pet_name}`}
              className="h-32 w-32 flex-shrink-0 rounded-lg border border-slate-200 object-cover"
            />
          ) : (
            <div className="h-32 w-32 flex-shrink-0 rounded-lg border border-dashed border-slate-300 flex items-center justify-center text-xs text-slate-400">
              No photo
            </div>
          )}
          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 flex-1">
            <Detail label="Name" value={app.pet_name} />
            <Detail label="Species" value={pet?.species ? humanise(pet.species) : ''} />
            <Detail label="Breed" value={pet?.breed} />
            <Detail label="Age" value={ageLabel(pet?.age_months)} />
            <Detail label="Gender" value={pet?.gender ? humanise(pet.gender) : ''} />
            <Detail label="Size" value={pet?.size ? humanise(pet.size) : ''} />
            <Detail label="Color" value={pet?.color} />
            <Detail label="Pet status" value={pet ? <StatusBadge status={pet.status} /> : ''} />
            <Detail label="Vaccinated" value={pet ? (pet.is_vaccinated ? 'Yes' : 'No') : ''} />
            <Detail label="Neutered" value={pet ? (pet.is_neutered ? 'Yes' : 'No') : ''} />
          </dl>
        </div>
        {pet?.description && (
          <dl className="mt-4">
            <Detail label="Description" value={pet.description} />
          </dl>
        )}
        {!pet && (
          <p className="mt-4 text-sm text-slate-500">
            Pet details could not be loaded; only the application's pet name is shown.
          </p>
        )}
      </SectionCard>

      <SectionCard title="Application Information">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Detail label="Why do you want to adopt this pet?" value={app.why_adopt} />
          <Detail label="Experience with pets" value={app.experience_with_pets} />
          <Detail label="Living situation" value={app.living_situation} />
          <Detail
            label="Other pets"
            value={app.has_other_pets ? app.other_pets_description || 'Yes' : 'No'}
          />
          <Detail label="References" value={app.references} />
          <Detail label="Additional notes from the adopter" value={app.additional_notes} />
        </dl>
      </SectionCard>

      <SectionCard title="Uploaded Documents">
        <div className="mb-5">
          <h4 className="text-sm font-medium text-slate-700 mb-2">Required documents</h4>
          <ul className="space-y-1">
            {REQUIRED_DOCUMENTS.map((required) => {
              const present = uploadedTypes.has(required.type);
              return (
                <li key={required.type} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className={present ? 'text-green-600' : 'text-red-600'} aria-hidden="true">
                    {present ? '\u2713' : '\u2715'}
                  </span>
                  <span className="text-slate-800">{required.label}</span>
                  <span className={present ? 'text-green-700' : 'text-red-700'}>
                    {present ? 'Submitted' : 'Not submitted'}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-500">
            No documents are attached to this application.
          </p>
        ) : (
          <ul className="divide-y divide-slate-200 border-t border-slate-200">
            {documents.map((doc) => (
              <li key={doc.id} className="py-3 flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900">
                    {humanise(doc.document_type)}
                  </p>
                  <p className="text-sm text-slate-600 break-all">{doc.original_filename}</p>
                  <p className="text-xs text-slate-500">
                    {formatFileSize(doc.file_size)} &middot; uploaded{' '}
                    {formatDateTime(doc.created_at)}
                    {doc.uploaded_by_email ? ` by ${doc.uploaded_by_email}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => viewDocument(doc)}
                    disabled={busyDocument === doc.id}
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-700 disabled:opacity-50"
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => downloadDocument(doc)}
                    disabled={busyDocument === doc.id}
                    className="text-sm font-medium text-slate-600 hover:text-slate-800 disabled:opacity-50"
                  >
                    Download
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Internal staff notes">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-slate-500">
            Only staff and administrators can see these notes.
          </p>
          <Button onClick={saveNotes} disabled={busy}>
            Save Notes
          </Button>
        </div>
        <label className="block">
          <span className="sr-only">Internal staff notes</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="Internal notes (not visible to the adopter)"
          />
        </label>
      </SectionCard>

      {app.rejection_reason && !allowed.includes('rejected') && (
        <SectionCard title="Rejection reason">
          <p className="text-sm text-red-700 whitespace-pre-wrap">{app.rejection_reason}</p>
        </SectionCard>
      )}

      {allowed.length > 0 && (
        <SectionCard title="Review decision">
          {allowed.includes('rejected') && (
            <div className="mb-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">
                  Rejection reason <span className="text-red-600">(required to reject)</span>
                </span>
                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={3}
                  placeholder="Explain why this application is being rejected — the adopter will see this."
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </label>
            </div>
          )}
          <div className="flex flex-wrap gap-3">
            {allowed.includes('approved') && (
              <Button onClick={() => transition('approved')} disabled={busy}>
                Approve Application
              </Button>
            )}
            {allowed.includes('rejected') && (
              <Button
                variant="danger"
                onClick={() => transition('rejected')}
                disabled={busy || !rejectionReason.trim()}
              >
                Reject Application
              </Button>
            )}
            {allowed.includes('pending_documents') && (
              <Button
                variant="secondary"
                onClick={() => transition('pending_documents')}
                disabled={busy}
              >
                Request Missing Documents
              </Button>
            )}
            {allowed.includes('additional_info_requested') && (
              <Button
                variant="outline"
                onClick={() => transition('additional_info_requested')}
                disabled={busy}
              >
                Request Additional Info
              </Button>
            )}
            {allowed.includes('under_review') && (
              <Button variant="outline" onClick={() => transition('under_review')} disabled={busy}>
                Mark Under Review
              </Button>
            )}
            {allowed.includes('submitted') && (
              <Button variant="outline" onClick={() => transition('submitted')} disabled={busy}>
                Mark Submitted
              </Button>
            )}
            {allowed.includes('cancelled') && (
              <Button variant="outline" onClick={() => transition('cancelled')} disabled={busy}>
                Cancel Application
              </Button>
            )}
          </div>
          {busy && <p className="mt-3 text-sm text-slate-500">Saving…</p>}
        </SectionCard>
      )}
    </div>
  );
}

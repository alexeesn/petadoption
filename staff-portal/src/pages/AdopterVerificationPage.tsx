import { useEffect, useState, useCallback } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table, Button, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { DecisionDialog } from '../components/DecisionDialog';
import { verificationService } from '../services/apiService';
import type { IdentityVerificationRequest } from '../types';
import { formatDisplayName } from '../utils/format';
import { useToast } from '../context/ToastContext';
import { Icon } from '../components/Icons';

type TabStatus = 'all' | 'pending_review' | 'verified' | 'rejected';

export default function AdopterVerificationPage() {
  const toast = useToast();
  const [requests, setRequests] = useState<IdentityVerificationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<TabStatus>('pending_review');
  const [selectedRequest, setSelectedRequest] = useState<IdentityVerificationRequest | null>(null);

  // Decision dialog states
  const [reviewDialog, setReviewDialog] = useState<{
    open: boolean;
    decision: 'approve' | 'reject';
  }>({ open: false, decision: 'approve' });

  // Selfie preview blob URL cache
  const [selfieBlobUrl, setSelfieBlobUrl] = useState<string | null>(null);
  const [selfieLoading, setSelfieLoading] = useState(false);

  const loadRequests = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, unknown> = {};
      if (activeTab !== 'all') {
        params.status = activeTab;
      }
      const res = await verificationService.list(params);
      const data = res.data;
      const list = Array.isArray(data) ? data : data.results || [];
      setRequests(list);

      // If currently selected request is in the list, update it
      if (selectedRequest) {
        const updated = list.find((r) => r.id === selectedRequest.id);
        if (updated) setSelectedRequest(updated);
      }
    } catch {
      setError('Failed to load identity verification requests.');
    } finally {
      setLoading(false);
    }
  }, [activeTab, selectedRequest]);

  useEffect(() => {
    loadRequests();
  }, [activeTab]);

  // When a request is selected, load its selfie preview
  useEffect(() => {
    if (!selectedRequest || !selectedRequest.has_selfie_with_id) {
      setSelfieBlobUrl(null);
      return;
    }
    let cancelled = false;
    setSelfieLoading(true);
    verificationService
      .downloadFile(selectedRequest.id, 'selfie_with_id')
      .then((res) => {
        if (!cancelled) {
          const url = URL.createObjectURL(res.data as Blob);
          setSelfieBlobUrl(url);
        }
      })
      .catch(() => {
        if (!cancelled) setSelfieBlobUrl(null);
      })
      .finally(() => {
        if (!cancelled) setSelfieLoading(false);
      });

    return () => {
      cancelled = true;
      if (selfieBlobUrl) {
        URL.revokeObjectURL(selfieBlobUrl);
      }
    };
  }, [selectedRequest?.id]);

  const handleDownloadFile = async (id: string, field: 'combined_pdf' | 'selfie_with_id', filename: string) => {
    try {
      const res = await verificationService.downloadFile(id, field);
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Could not download the verification file.');
    }
  };

  const handleReviewDecision = async (reason: string) => {
    if (!selectedRequest) return;
    const decision = reviewDialog.decision;
    const res = await verificationService.review(selectedRequest.id, decision, reason);
    const updated = res.data;
    setSelectedRequest(updated);
    setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    toast.success(
      decision === 'approve' ? 'Verification Approved' : 'Verification Rejected',
      decision === 'approve'
        ? `${updated.adopter_name || updated.adopter_email} is now verified to adopt pets.`
        : `Rejection notice recorded. Adopter can resubmit after correcting issues.`
    );
  };

  const tabs: { key: TabStatus; label: string }[] = [
    { key: 'pending_review', label: 'Pending Review' },
    { key: 'all', label: 'All Requests' },
    { key: 'verified', label: 'Verified' },
    { key: 'rejected', label: 'Rejected' },
  ];

  return (
    <div>
      <PageHeader
        title="Adopter Verification"
        subtitle="Review identity and general eligibility documents submitted by adopters"
      />

      {/* Status Filter Tabs */}
      <div className="flex border-b border-slate-200 mb-6 gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setActiveTab(tab.key);
              setSelectedRequest(null);
            }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.key
                ? 'border-primary-600 text-primary-700 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : selectedRequest ? (
        /* ── DETAIL VIEW ── */
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setSelectedRequest(null)}
              className="text-sm font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1"
            >
              &larr; Back to verification list
            </button>
            <StatusBadge status={selectedRequest.status} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Adopter Details & Review History */}
            <div className="space-y-6">
              <Card>
                <h3 className="text-base font-bold text-slate-900 mb-4 border-b border-slate-100 pb-2">
                  Adopter Profile
                </h3>
                <dl className="space-y-3 text-sm">
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Name</dt>
                    <dd className="mt-0.5 font-medium text-slate-900">
                      {formatDisplayName(selectedRequest.adopter_name) || 'Not set'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</dt>
                    <dd className="mt-0.5 text-slate-700">{selectedRequest.adopter_email}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Submission Date
                    </dt>
                    <dd className="mt-0.5 text-slate-700">
                      {selectedRequest.submitted_at
                        ? new Date(selectedRequest.submitted_at).toLocaleString()
                        : 'Not recorded'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Privacy Consent
                    </dt>
                    <dd className="mt-0.5 text-slate-700">
                      {selectedRequest.privacy_consent ? (
                        <span className="text-emerald-700 font-medium">
                          ✓ Agreed ({selectedRequest.consent_given_at ? new Date(selectedRequest.consent_given_at).toLocaleDateString() : 'Yes'})
                        </span>
                      ) : (
                        <span className="text-slate-400">No record</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </Card>

              {/* Review History */}
              <Card>
                <h3 className="text-base font-bold text-slate-900 mb-3 border-b border-slate-100 pb-2">
                  Review Details
                </h3>
                {selectedRequest.status === 'pending_review' ? (
                  <p className="text-xs text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-200">
                    Awaiting staff decision. Review the submitted documents and approve or reject below.
                  </p>
                ) : (
                  <dl className="space-y-2.5 text-xs text-slate-700">
                    <div>
                      <dt className="font-semibold text-slate-500 uppercase">Reviewer</dt>
                      <dd className="mt-0.5 font-medium text-slate-900">
                        {selectedRequest.reviewed_by_email || 'Staff'}
                      </dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-slate-500 uppercase">Decision Timestamp</dt>
                      <dd className="mt-0.5">
                        {selectedRequest.reviewed_at
                          ? new Date(selectedRequest.reviewed_at).toLocaleString()
                          : 'Not recorded'}
                      </dd>
                    </div>
                    {selectedRequest.rejection_reason && (
                      <div className="pt-2 border-t border-slate-100">
                        <dt className="font-semibold text-rose-700 uppercase">Rejection Reason</dt>
                        <dd className="mt-1 p-2.5 bg-rose-50 border border-rose-200 rounded text-rose-900 whitespace-pre-line text-xs font-mono">
                          {selectedRequest.rejection_reason}
                        </dd>
                      </div>
                    )}
                  </dl>
                )}
              </Card>

              {/* Review Decision Actions */}
              {selectedRequest.status === 'pending_review' && (
                <Card>
                  <h3 className="text-base font-bold text-slate-900 mb-3">Make Decision</h3>
                  <p className="text-xs text-slate-500 mb-4">
                    Approving marks this adopter verified and unlocks adoption application submission.
                    Rejecting requires a clear reason for the adopter.
                  </p>
                  <div className="flex flex-col gap-2.5">
                    <Button
                      variant="primary"
                      className="w-full justify-center bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => setReviewDialog({ open: true, decision: 'approve' })}
                    >
                      ✓ Approve Verification
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full justify-center text-rose-700 border-rose-300 hover:bg-rose-50"
                      onClick={() => setReviewDialog({ open: true, decision: 'reject' })}
                    >
                      ✕ Reject Verification
                    </Button>
                  </div>
                </Card>
              )}
            </div>

            {/* Right Columns: Submitted Verification Documents */}
            <div className="lg:col-span-2 space-y-6">
              {/* Document 1: Combined PDF */}
              <Card>
                <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Icon name="clipboard" className="w-5 h-5 text-primary-600" />
                      Combined Required Documents (PDF)
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Contains: Valid ID + Proof of Address + Barangay Certification
                    </p>
                  </div>
                  {selectedRequest.has_combined_pdf && (
                    <Button
                      variant="outline"
                      className="text-xs"
                      onClick={() =>
                        handleDownloadFile(
                          selectedRequest.id,
                          'combined_pdf',
                          `${selectedRequest.adopter_email}_combined_documents.pdf`
                        )
                      }
                    >
                      Download PDF
                    </Button>
                  )}
                </div>

                {selectedRequest.has_combined_pdf ? (
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center space-y-3">
                    <p className="text-sm text-slate-700">
                      The adopter has submitted their combined eligibility documents as a PDF.
                    </p>
                    <Button
                      variant="primary"
                      onClick={() =>
                        handleDownloadFile(
                          selectedRequest.id,
                          'combined_pdf',
                          `${selectedRequest.adopter_email}_combined_documents.pdf`
                        )
                      }
                    >
                      Download &amp; Inspect Combined PDF
                    </Button>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400 italic">No combined PDF uploaded.</p>
                )}
              </Card>

              {/* Document 2: Selfie with Valid ID */}
              <Card>
                <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Icon name="user" className="w-5 h-5 text-primary-600" />
                      Selfie with Valid ID
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Check that the adopter&apos;s face and the details on the ID match and are legible
                    </p>
                  </div>
                  {selectedRequest.has_selfie_with_id && (
                    <Button
                      variant="outline"
                      className="text-xs"
                      onClick={() =>
                        handleDownloadFile(
                          selectedRequest.id,
                          'selfie_with_id',
                          `${selectedRequest.adopter_email}_selfie_with_id.jpg`
                        )
                      }
                    >
                      Download Image
                    </Button>
                  )}
                </div>

                {selectedRequest.has_selfie_with_id ? (
                  <div className="space-y-4">
                    {selfieLoading ? (
                      <Loading />
                    ) : selfieBlobUrl ? (
                      <div className="p-2 bg-slate-900 rounded-xl max-w-md mx-auto flex justify-center">
                        <img
                          src={selfieBlobUrl}
                          alt="Selfie with valid ID"
                          className="max-h-96 object-contain rounded-lg"
                        />
                      </div>
                    ) : (
                      <div className="p-6 bg-slate-50 rounded-xl border border-slate-200 text-center">
                        <p className="text-sm text-slate-600 mb-2">Image preview unavailable.</p>
                        <Button
                          variant="outline"
                          onClick={() =>
                            handleDownloadFile(
                              selectedRequest.id,
                              'selfie_with_id',
                              `${selectedRequest.adopter_email}_selfie_with_id.jpg`
                            )
                          }
                        >
                          Download Photo File
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400 italic">No selfie image uploaded.</p>
                )}
              </Card>
            </div>
          </div>
        </div>
      ) : requests.length === 0 ? (
        <Card>
          <Empty message={`No verification requests found in '${activeTab.replace('_', ' ')}'.`} />
        </Card>
      ) : (
        /* ── TABLE VIEW ── */
        <Card>
          <Table headers={['Adopter Name', 'Email', 'Status', 'Submitted', 'Reviewer', 'Action']}>
            {requests.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">
                  {formatDisplayName(r.adopter_name) || <span className="text-slate-400 italic">Not set</span>}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{r.adopter_email}</td>
                <td className="px-4 py-3 text-sm">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {r.reviewed_by_email || '—'}
                </td>
                <td className="px-4 py-3 text-sm">
                  <button
                    type="button"
                    onClick={() => setSelectedRequest(r)}
                    className="font-semibold text-primary-600 hover:text-primary-800 text-xs uppercase tracking-wide hover:underline"
                  >
                    {r.status === 'pending_review' ? 'Review Request' : 'View Details'}
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      {/* Decision Dialog */}
      {reviewDialog.open && selectedRequest && (
        <DecisionDialog
          title={
            reviewDialog.decision === 'approve'
              ? 'Approve Identity Verification'
              : 'Reject Identity Verification'
          }
          description={
            reviewDialog.decision === 'approve'
              ? `Confirm that you have inspected the combined PDF and selfie with ID for ${
                  selectedRequest.adopter_name || selectedRequest.adopter_email
                } and verified their eligibility.`
              : `Specify the reason why this verification cannot be approved. This reason will be visible to the adopter so they can correct their documents and resubmit.`
          }
          requireReason={reviewDialog.decision === 'reject'}
          confirmationLabel={
            reviewDialog.decision === 'approve'
              ? 'I confirm that the submitted identity documents and selfie meet verification standards.'
              : 'I confirm that this verification request is rejected for the stated reason.'
          }
          onConfirm={handleReviewDecision}
          onClose={() => setReviewDialog({ open: false, decision: 'approve' })}
        />
      )}
    </div>
  );
}

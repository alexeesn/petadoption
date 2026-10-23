import { useToast } from '../context/ToastContext';
import { useEffect, useRef, useState } from 'react';
import {
  Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select,
} from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adoptionService, applicationService } from '../services/apiService';
import type { AdoptionRecord, Application, PaginatedResponse } from '../types';
import { formatDate, formatDateTime, formatCurrency } from '../utils/format';
import { DecisionDialog } from '../components/DecisionDialog';

/** Matches AdoptionRecord.Status.choices in backend/apps/adoptions/models.py. */
const STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'returned', label: 'Returned' },
];

function shortId(value: string): string {
  return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}

function humanise(value: string): string {
  return value.replace(/_/g, ' ');
}

/** Filename convention for the generated report: pawconnect-adoption-records-YYYY-MM-DD.pdf */
function reportFilename(): string {
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `pawconnect-adoption-records-${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.pdf`;
}

/**
 * Adoption Records (browsing, completion, and individual PDF download).
 *
 * Records are created server-side when staff confirm an onsite visit date; the
 * permanent transaction ID is generated and stored by the backend only when a
 * record is completed. Scheduled records can be completed from here via the
 * same canonical endpoint the Application Review page uses
 * (POST /api/applications/{id}/complete-adoption/), which re-validates the
 * approved application, confirmed appointment, fully paid fee, and an explicit
 * physical-handover confirmation. Completed adoptions have individual PDF
 * certificate downloads.
 */
export default function AdoptionsPage() {
  const toast = useToast();
  const [returningRecord, setReturningRecord] = useState<AdoptionRecord | null>(null);
  const [returnSuccess, setReturnSuccess] = useState('');
  const [cancellingRecord, setCancellingRecord] = useState<AdoptionRecord | null>(null);
  const [cancellationSuccess, setCancellationSuccess] = useState('');
  const [records, setRecords] = useState<AdoptionRecord[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // ----- Complete Adoption (per scheduled record) -----
  const [completionRecord, setCompletionRecord] = useState<AdoptionRecord | null>(null);
  const [completionApp, setCompletionApp] = useState<Application | null>(null);
  const [eligibilityLoading, setEligibilityLoading] = useState(false);
  const [handoverChecked, setHandoverChecked] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [completionError, setCompletionError] = useState('');
  const dialogRef = useRef<HTMLDialogElement>(null);

  const load = () => {
    setLoading(true);
    setError('');
    const params: Record<string, unknown> = { page };
    if (statusFilter) params.status = statusFilter;
    adoptionService
      .list(params)
      .then((res) => {
        const data = res.data as PaginatedResponse<AdoptionRecord>;
        setRecords(data.results);
        setCount(data.count);
        setHasPrevious(Boolean(data.previous));
        setHasNext(Boolean(data.next));
      })
      .catch(() => setError('Failed to load adoption records.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [page, statusFilter]);

  /**
   * Open the completion confirmation dialog for a scheduled record and load
   * the application so eligibility reflects current server-side data (the
   * backend re-validates on submit; this only drives the UI state).
   */
  const openCompletion = (rec: AdoptionRecord) => {
    setCompletionRecord(rec);
    setCompletionApp(null);
    setHandoverChecked(false);
    setCompleting(false);
    setCompletionError('');
    setEligibilityLoading(true);
    applicationService
      .retrieve(rec.application_id)
      .then((res) => setCompletionApp(res.data as Application))
      .catch(() => setCompletionApp(null))
      .finally(() => setEligibilityLoading(false));
  };

  const closeCompletion = () => {
    setCompletionRecord(null);
  };

  // Open the native <dialog> whenever a record is selected for completion.
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (completionRecord && !el.open) el.showModal();
    else if (!completionRecord && el.open) el.close();
  }, [completionRecord]);

  // Escape-to-close fallback for browsers that do not fire the cancel event.
  useEffect(() => {
    if (!completionRecord) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeCompletion();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [completionRecord]);

  /**
   * Submit to the canonical adoption-completion endpoint
   * (POST /api/applications/{id}/complete-adoption/, the same endpoint used by
   * the Application Review page), then refresh the table. The backend owns all
   * validation: approved application, confirmed appointment, fully paid fee,
   * and the strict boolean handover confirmation carried by the service call.
   */
  const confirmCompletion = () => {
    if (!completionRecord) return;
    setCompleting(true);
    setCompletionError('');
    applicationService
      .completeAdoption(completionRecord.application_id)
      .then(() => {
        toast.success('Adoption completed', `${completionRecord.pet_name} is now marked as adopted.`);
        closeCompletion();
        load();
      })
      .catch((e) => {
        const data = (e as { response?: { data?: { error?: string } } }).response?.data;
        setCompletionError(data?.error || 'Failed to complete the adoption. Please try again.');
      })
      .finally(() => setCompleting(false));
  };

  // Eligibility checklist shown in the dialog, mirroring the backend gates in
  // complete_application_adoption() (backend/apps/adoptions/services.py).
  const requirements = completionRecord
    ? [
        {
          met: completionApp?.status === 'approved',
          label: 'Application approved',
          message: completionApp
            ? `The adoption application must be approved first (current status: ${humanise(completionApp.status)}).`
            : 'The adoption application for this record could not be verified.',
        },
        {
          met: Boolean(completionRecord.appointment_id) && completionRecord.appointment_status === 'confirmed',
          label: 'Confirmed onsite visit date',
          message: 'A confirmed onsite visit appointment is required before the pet can be handed over.',
        },
        {
          met: completionApp?.onsite_visit?.date_reached === true,
          label: 'Confirmed appointment date reached (Philippine time)',
          message: completionApp?.onsite_visit?.message || 'The confirmed appointment date must be reached before adoption completion.',
        },
        {
          met: Boolean(completionRecord.is_fee_paid),
          label: `Adoption fee paid (₱${completionRecord.adoption_fee ?? '500.00'})`,
          message: `The adoption fee must be fully paid before completion (total completed: ${formatCurrency(completionRecord.total_paid ?? '0.00')}).`,
        },
      ]
    : [];
  const completionEligible = completionRecord !== null && completionApp !== null && requirements.every((r) => r.met);

  const clearFilters = () => {
    setStatusFilter('');
    setExportError('');
    setPage(1);
  };

  /** Download the current-filter adoption records as an aggregate PDF report */
  const exportPdf = () => {
    setExporting(true);
    setExportError('');
    setError('');
    const params: Record<string, unknown> = {};
    if (statusFilter) params.status = statusFilter;
    adoptionService
      .exportPdf(params)
      .then((res) => {
        const blob = res.data as Blob;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = reportFilename();
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      })
      .catch(async (e: unknown) => {
        let message = 'Failed to export the PDF.';
        const data = (e as { response?: { data?: unknown } } | undefined)?.response?.data;
        if (data instanceof Blob) {
          try {
            const parsed = JSON.parse(await data.text()) as Record<string, unknown>;
            if (typeof parsed.detail === 'string') {
              message = parsed.detail;
            } else {
              const parts: string[] = [];
              for (const [key, val] of Object.entries(parsed)) {
                const label = key === 'non_field_errors' ? '' : `${key.replace(/_/g, ' ')}: `;
                if (Array.isArray(val)) parts.push(`${label}${(val as string[]).join(', ')}`);
                else if (typeof val === 'string') parts.push(`${label}${val}`);
              }
              if (parts.length > 0) message = parts.join(' · ');
            }
          } catch {
            // Not JSON
          }
        }
        setExportError(message);
      })
      .finally(() => setExporting(false));
  };

  /** Download the certificate or return record from the current saved status. */
  const downloadRecordPdf = (rec: AdoptionRecord) => {
    setDownloadingId(rec.id);
    setExportError('');
    adoptionService
      .recordPdf(rec.id)
      .then((res) => {
        const blob = res.data as Blob;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        const refSlug = rec.transaction_id || rec.id.slice(0, 8);
        const prefix = rec.status === 'returned' ? 'adoption-return'
          : rec.status === 'cancelled' ? 'adoption-cancelled' : 'adoption';
        anchor.download = `pawconnect-${prefix}-${refSlug}.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      })
      .catch(() => {
        setExportError('Failed to download individual adoption record PDF.');
      })
      .finally(() => setDownloadingId(null));
  };

  return (
    <div>
      <PageHeader
        title="Adoption Records"
        subtitle="Completed, returned and cancelled adoptions have individual PDF downloads. Each PDF includes the downloading staff member and current generation date. Use Export All Filtered PDF for aggregate records."
      />
      {cancellationSuccess && <p role="status" className="mb-4 text-sm text-green-800">{cancellationSuccess}</p>}
      {returnSuccess && <p role="status" className="mb-4 text-sm text-green-800">{returnSuccess}</p>}

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select
          label="Status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          options={STATUS_FILTERS}
        />
        {statusFilter && (
          <Button variant="outline" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={exportPdf}
          disabled={exporting}
        >
          {exporting ? 'Preparing PDF…' : 'Export All Filtered PDF'}
        </Button>
      </div>
      {exportError && (
        <p role="alert" className="mb-4 text-sm text-red-600">
          {exportError}
        </p>
      )}

      <p className="mb-2 text-xs text-slate-500">
        Status legend:{' '}
        {STATUS_FILTERS.filter((opt) => opt.value).map((opt) => (
          <StatusBadge key={opt.value} status={opt.value} />
        ))}
      </p>
      <p className="mb-4 text-xs text-slate-500">
        Records with status <span className="font-medium text-sky-700">Scheduled</span> can be
        completed from the <strong>Action</strong> column once the onsite visit is confirmed and the
        adoption fee is fully paid. Records with status{' '}
        <span className="font-medium text-green-700">Completed</span> are finalized adoptions — they
        carry a permanent transaction ID and can be downloaded as an individual official PDF.
      </p>

      {loading ? (
        <Loading label="Loading adoption records..." />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : records.length === 0 ? (
        <Card>
          <Empty message="No adoption records match these filters." />
        </Card>
      ) : (
        <>
          <Card>
            <Table
              headers={[
                'Transaction ID', 'Pet', 'Adopter', 'Application', 'Status',
                'Completed', 'Completed by', 'Appointment', 'Action',
              ]}
            >
              {records.map((rec) => (
                <tr key={rec.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                    {rec.transaction_id || '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {rec.pet_name}
                    <span className="ml-1 text-xs text-slate-400">({shortId(rec.pet)})</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {rec.adopter_email}
                    <span className="ml-1 text-xs text-slate-400">({shortId(rec.adopter)})</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500" title={rec.application_id}>
                    {shortId(rec.application_id)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={rec.status} />
                    {rec.status === 'cancelled' && <div className="mt-1 max-w-xs text-xs text-slate-600">
                      <p>{rec.cancellation_reason || 'No cancellation reason recorded.'}</p>
                      {rec.cancelled_at && <p>{formatDateTime(rec.cancelled_at)}</p>}
                    </div>}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {rec.completed_at
                      ? formatDateTime(rec.completed_at)
                      : rec.completed_date
                        ? formatDate(rec.completed_date)
                        : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">{rec.staff_email || '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {rec.appointment_id && rec.appointment_date
                      ? `${formatDate(rec.appointment_date)}`
                      : '—'}
                    {rec.appointment_status && <div className="mt-1"><StatusBadge status={rec.appointment_status} /></div>}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {rec.status === 'completed' ? (
                      <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        className="text-xs px-2.5 py-1"
                        onClick={() => downloadRecordPdf(rec)}
                        disabled={downloadingId === rec.id}
                      >
                        {downloadingId === rec.id ? 'PDF…' : 'Download PDF'}
                      </Button>
                      <Button variant="danger" className="text-xs px-2.5 py-1"
                        onClick={() => { setReturnSuccess(''); setReturningRecord(rec); }}>
                        Mark as Returned
                      </Button>
                      </div>
                    ) : rec.status === 'returned' || rec.status === 'cancelled' ? (
                      <Button variant="outline" className="text-xs px-2.5 py-1"
                        onClick={() => downloadRecordPdf(rec)} disabled={downloadingId === rec.id}>
                        {downloadingId === rec.id ? 'PDF…' : rec.status === 'returned' ? 'Download Return PDF' : 'Download Cancellation PDF'}
                      </Button>
                    ) : rec.status === 'scheduled' ? (
                      <div className="flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        className="text-xs px-2.5 py-1"
                        onClick={() => openCompletion(rec)}
                        disabled={completing || rec.onsite_visit?.date_reached !== true}
                      >
                        Complete Adoption
                      </Button>
                      {rec.onsite_visit?.message && <p className="w-full max-w-xs text-xs text-slate-600">{rec.onsite_visit.message}</p>}
                      <Button variant="danger" className="text-xs px-2.5 py-1"
                        disabled={completing} onClick={() => { setCancellationSuccess(''); setCancellingRecord(rec); }}>
                        Cancel Adoption
                      </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
          </Card>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              disabled={!hasPrevious || loading}
              onClick={() => setPage(Math.max(1, page - 1))}
            >
              ← Previous
            </Button>
            <span className="text-sm text-slate-600">
              Page {page} · {count} total record{count === 1 ? '' : 's'}
            </span>
            <Button variant="outline" disabled={!hasNext || loading} onClick={() => setPage(page + 1)}>
              Next →
            </Button>
          </div>
        </>
      )}
      {returningRecord && <DecisionDialog title="Mark as Returned"
        description={`Record that ${returningRecord.pet_name} has been returned by ${returningRecord.adopter_email}. The pet will become Available for adoption again. The original adoption and payment history are retained; no automatic refund is issued.`}
        confirmationLabel="I confirm the pet has been physically returned to the shelter."
        onClose={() => setReturningRecord(null)} onConfirm={async (reason) => {
          await adoptionService.markReturned(returningRecord.id, reason);
          toast.success('Adoption returned', `${returningRecord.pet_name} is now available for adoption again.`);
          setReturnSuccess('Return recorded. The pet is Available again; payment records and receipts are retained without an automatic refund.');
          load();
        }} />}
      {cancellingRecord && <DecisionDialog title="Cancel Adoption"
        description={`Cancel ${cancellingRecord.pet_name}'s Scheduled adoption for ${cancellingRecord.adopter_email}. This closes the application and active appointments. Existing payments are retained; no automatic refund is issued.`}
        onClose={() => setCancellingRecord(null)} onConfirm={async (reason) => {
          await adoptionService.cancel(cancellingRecord.id, reason);
          toast.success('Adoption cancelled', `${cancellingRecord.pet_name}'s adoption record has been updated.`);
          setCancellationSuccess('Adoption cancelled. Its application and active appointments are closed; payment history is retained.');
          load();
        }} />}
      {completionRecord && (
        <dialog
          ref={dialogRef}
          onCancel={(e) => {
            e.preventDefault();
            closeCompletion();
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) closeCompletion();
          }}
          aria-label="Complete adoption confirmation"
          aria-modal="true"
          className={[
            'bg-transparent p-0 border-0 outline-none',
            'fixed inset-0 m-0 max-h-none max-w-none w-screen h-screen',
            'bg-black/50',
            'flex items-center justify-center',
            'z-50',
          ].join(' ')}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            role="document"
            className="relative max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-2xl"
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Complete Adoption</h3>
                <p className="text-xs text-slate-500">
                  Confirm the onsite visit finished and the pet was physically handed over.
                </p>
              </div>
              <button
                type="button"
                onClick={closeCompletion}
                aria-label="Close completion dialog"
                className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <span aria-hidden="true" className="text-lg leading-none">×</span>
              </button>
            </div>

            {eligibilityLoading ? (
              <Loading label="Checking completion eligibility…" />
            ) : (
              <>
                {/* Record summary: pet, adopter, appointment, and payment totals */}
                <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div>
                    <dt className="text-xs text-slate-500">Pet</dt>
                    <dd className="font-medium text-slate-900">{completionRecord.pet_name}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Adopter</dt>
                    <dd className="font-medium text-slate-900">{completionRecord.adopter_email}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Appointment</dt>
                    <dd className="font-medium text-slate-900">
                      {completionRecord.appointment_id
                        ? formatDate(completionRecord.appointment_date ?? undefined)
                        : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Adoption fee</dt>
                    <dd className="font-medium text-slate-900">
                      {formatCurrency(completionRecord.adoption_fee ?? completionApp?.adoption_fee ?? null)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Paid</dt>
                    <dd className="font-medium text-slate-900">
                      {formatCurrency(completionRecord.total_paid ?? completionApp?.total_paid ?? null)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Balance</dt>
                    <dd className={`font-medium ${completionRecord.is_fee_paid ? 'text-green-700' : 'text-slate-900'}`}>
                      {formatCurrency(
                        Math.max(
                          Number(completionRecord.adoption_fee ?? completionApp?.adoption_fee ?? 0) -
                            Number(completionRecord.total_paid ?? completionApp?.total_paid ?? 0),
                          0,
                        ),
                      )}
                    </dd>
                  </div>
                </dl>

                {/* Eligibility requirements - each missing item explains what is needed */}
                <ul className="mb-4 space-y-1.5 text-sm">
                  {requirements.map((req) => (
                    <li
                      key={req.label}
                      className={`flex items-start gap-2 ${req.met ? 'text-slate-600' : 'font-medium text-red-700'}`}
                    >
                      <span aria-hidden="true" className="mt-0.5">
                        {req.met ? '✓' : '✗'}
                      </span>
                      <span>{req.met ? req.label : req.message}</span>
                    </li>
                  ))}
                </ul>

                {completionError && (
                  <div
                    role="alert"
                    className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                  >
                    {completionError}
                  </div>
                )}

                <label className="mb-4 flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={handoverChecked}
                    onChange={(e) => setHandoverChecked(e.target.checked)}
                    disabled={completing || !completionEligible}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span>
                    I confirm the pet has been <strong>physically handed over</strong> to the
                    adopter. This is required to complete the adoption.
                  </span>
                </label>

                <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
                  <Button variant="outline" onClick={closeCompletion} disabled={completing}>
                    Cancel
                  </Button>
                  <Button
                    onClick={confirmCompletion}
                    disabled={completing || !handoverChecked || !completionEligible}
                  >
                    {completing ? 'Completing…' : 'Complete Adoption'}
                  </Button>
                </div>
              </>
            )}
          </div>
        </dialog>
      )}
    </div>
  );
}

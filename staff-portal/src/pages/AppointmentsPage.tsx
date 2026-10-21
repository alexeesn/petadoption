import { useEffect, useState } from 'react';
import { Card, Loading, Empty, StatusBadge, Button, Input, Select, Textarea } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { applicationService, appointmentService, paymentService } from '../services/apiService';
import type { Appointment, PaymentSummary } from '../types';
import { formatCurrency, formatDate } from '../utils/format';

const STATUS_FILTERS = [
  { value: 'pending_confirmation', label: 'Pending confirmation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
];

/** Reuses Payment.Method choices in backend/apps/payments/models.py. */
const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'gcash', label: 'GCash' },
  { value: 'paymaya', label: 'PayMaya' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'online', label: 'Online' },
];

function humanise(value: string): string {
  return value.replace(/_/g, ' ');
}

/**
 * Read the most useful error text from an axios-style failure. Mirrors the
 * parsing used on the application detail page so backend validation errors
 * (e.g. "The required adoption fee ... has not been fully paid") reach staff.
 */
function readError(e: unknown, fallback: string): string {
  const data = (e as { response?: { data?: unknown } } | undefined)?.response?.data;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (typeof obj.error === 'string') return obj.error;
    if (typeof obj.detail === 'string') return obj.detail;
    const parts: string[] = [];
    for (const [key, val] of Object.entries(obj)) {
      const label = key === 'non_field_errors' ? '' : `${key.replace(/_/g, ' ')}: `;
      if (Array.isArray(val)) {
        parts.push(...(val as string[]).map((v) => `${label}${v}`));
      } else if (typeof val === 'string') {
        parts.push(`${label}${val}`);
      }
    }
    if (parts.length > 0) return parts.join(' · ');
  }
  return fallback;
}

interface OnsiteTransactionPanelProps {
  appointment: Appointment;
  /** undefined while the summary is loading, the value once it has loaded. */
  summary?: PaymentSummary;
  summaryError: boolean;
  onPaymentRecorded: (applicationId: string) => void;
  onTurnoverCompleted: (applicationId: string) => void;
  onRetrySummary: (applicationId: string) => void;
}

/**
 * Onsite adoption transaction for a *confirmed* appointment.
 *
 * Uses the backend ``payment-summary`` endpoint as the source of truth for the
 * fee, the completed-payment total, and turnover eligibility — the fee is never
 * hardcoded here. Payments go through the staff-only ``record-onsite`` endpoint
 * (the backend forces status=completed and generates the receipt), and turnover
 * goes through the validated ``complete-adoption`` endpoint with an explicit
 * boolean ``confirmed: true``. Nothing ever marks the adoption complete
 * optimistically; the UI only reports what the backend accepted.
 */
function OnsiteTransactionPanel({
  appointment,
  summary,
  summaryError,
  onPaymentRecorded,
  onTurnoverCompleted,
  onRetrySummary,
}: OnsiteTransactionPanelProps) {
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('cash');
  const [notes, setNotes] = useState('');
  const [received, setReceived] = useState(false);
  const [handover, setHandover] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [turnoverBusy, setTurnoverBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (summaryError) {
    return (
      <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4">
        <p className="text-sm text-red-800" role="alert">
          Could not load the payment summary for this application.
        </p>
        <Button
          variant="outline"
          className="mt-2"
          onClick={() => onRetrySummary(appointment.application)}
        >
          Try again
        </Button>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="mt-4 rounded-md border border-slate-200 p-4">
        <Loading label="Loading payment summary..." />
      </div>
    );
  }

  const feeNumber = Number(summary.adoption_fee || '0');
  const paidNumber = Number(summary.total_paid || '0');
  const balance = Math.max(feeNumber - paidNumber, 0);
  // Prefill with the backend fee until staff type a different amount.
  const displayAmount = amount !== '' ? amount : summary.adoption_fee;
  const completed = summary.is_fee_paid && !summary.turnover_eligible;

  const recordPayment = () => {
    setError('');
    setSuccess('');
    const value = Number(displayAmount);
    if (displayAmount === '' || !Number.isFinite(value) || value <= 0) {
      setError('Enter the received amount (greater than zero).');
      return;
    }
    if (!received) {
      setError('Confirm that the payment has actually been received before recording it.');
      return;
    }
    setPaymentBusy(true);
    paymentService
      .recordOnsite({
        application: appointment.application,
        amount: displayAmount,
        method,
        notes: notes.trim(),
        payment_received: true,
      })
      .then((res: { data: { receipt_number?: string } }) => {
        setSuccess(
          `Payment of ${formatCurrency(displayAmount)} recorded` +
            (res.data.receipt_number ? ` · Receipt ${res.data.receipt_number}` : '') +
            '. Recording the payment does not complete the adoption.',
        );
        setAmount('');
        setNotes('');
        setReceived(false);
        onPaymentRecorded(appointment.application);
      })
      .catch((e: unknown) => setError(readError(e, 'Failed to record the payment.')))
      .finally(() => setPaymentBusy(false));
  };

  const confirmTurnover = () => {
    setError('');
    setSuccess('');
    if (!handover) {
      setError(
        'Confirm that the pet has been physically handed over before completing the adoption.',
      );
      return;
    }
    setTurnoverBusy(true);
    applicationService
      .completeAdoption(appointment.application)
      .then(() => {
        setSuccess(
          `Adoption completed — ${appointment.pet_name} has been handed over to ` +
            `${appointment.adopter_name || appointment.adopter_email}.`,
        );
        setHandover(false);
        onTurnoverCompleted(appointment.application);
      })
      .catch((e: unknown) =>
        // The backend rejects with a useful message (e.g. unpaid balance). The
        // UI has changed nothing locally on failure, so the current state stands.
        setError(readError(e, 'Could not complete the adoption.')),
      )
      .finally(() => setTurnoverBusy(false));
  };

  return (
    <div className="mt-4 rounded-md border border-slate-200 p-4">
      <h4 className="text-sm font-semibold text-slate-800">Onsite transaction</h4>

      <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <p className="text-xs text-slate-500">Adoption fee</p>
          <p className="text-sm font-semibold text-slate-900">{formatCurrency(feeNumber)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total completed payments</p>
          <p className="text-sm font-semibold text-slate-900">{formatCurrency(paidNumber)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Remaining balance</p>
          <p className={`text-sm font-semibold ${balance > 0 ? 'text-red-700' : 'text-slate-900'}`}>
            {formatCurrency(balance)}
          </p>
        </div>
      </div>

      <p className="mt-2 text-xs text-slate-500">
        Payment status:{' '}
        <StatusBadge status={summary.is_fee_paid ? 'paid' : paidNumber > 0 ? 'partial' : 'unpaid'} />
        {' '}· Turnover eligibility:{' '}
        {summary.turnover_eligible ? (
          <span className="font-medium text-green-700">Eligible</span>
        ) : (
          <span className="font-medium text-slate-500">Not eligible</span>
        )}
      </p>

      {summary.payments.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-slate-500">Recorded payments</p>
          <ul className="mt-1 space-y-1.5 text-xs text-slate-600">
            {summary.payments.map((payment) => (
              <li key={payment.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {formatDate(payment.payment_date ?? undefined)} · {humanise(payment.method)} ·{' '}
                  <span className="font-medium">{formatCurrency(payment.amount)}</span>
                </span>
                <span className="text-slate-500">
                  {payment.receipt_number ? `Receipt ${payment.receipt_number}` : humanise(payment.status)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      {success && (
        <p
          role="status"
          className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800"
        >
          {success}
        </p>
      )}

      {completed ? (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <p className="text-sm text-slate-600">
            This adoption has been completed — the fee is paid and turnover is no longer
            available for this application.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-4 border-t border-slate-200 pt-3">
            <h5 className="text-sm font-semibold text-slate-800">Record payment</h5>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl">
              <Input
                label="Amount received"
                type="number"
                step="0.01"
                min="0.01"
                value={displayAmount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  setError('');
                }}
              />
              <Select
                label="Payment method"
                value={method}
                onChange={(e) => {
                  setMethod(e.target.value);
                  setError('');
                }}
                options={PAYMENT_METHODS}
              />
            </div>
            <div className="mt-3 max-w-xl">
              <Textarea
                label="Notes (optional)"
                value={notes}
                rows={2}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. cash received at the center"
              />
            </div>
            <label className="mt-3 inline-flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={received}
                onChange={(e) => {
                  setReceived(e.target.checked);
                  setError('');
                }}
                disabled={paymentBusy || turnoverBusy}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span>
                I confirm the payment has <strong>actually been received</strong> in full.
              </span>
            </label>
            <div className="mt-3">
              <Button onClick={recordPayment} disabled={paymentBusy || turnoverBusy}>
                {paymentBusy ? 'Recording payment…' : 'Record payment'}
              </Button>
            </div>
          </div>
<div className="mt-4 border-t border-slate-200 pt-3">
            <h5 className="text-sm font-semibold text-slate-800">Confirm pet turnover</h5>
            {!summary.is_fee_paid && (
              <p className="mt-2 text-sm text-slate-600">
                Record the full adoption fee before confirming turnover. Remaining balance:{' '}
                <span className="font-medium text-red-700">{formatCurrency(balance)}</span>
              </p>
            )}
            <label className="mt-2 inline-flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={handover}
                onChange={(e) => {
                  setHandover(e.target.checked);
                  setError('');
                }}
                disabled={paymentBusy || turnoverBusy || !summary.turnover_eligible}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span>
                I confirm the pet has been <strong>physically handed over</strong> to the adopter.
              </span>
            </label>
            <div className="mt-3">
              <Button
                variant="secondary"
                onClick={confirmTurnover}
                disabled={!handover || !summary.turnover_eligible || paymentBusy || turnoverBusy}
              >
                {turnoverBusy ? 'Confirming…' : 'Confirm pet turnover'}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Review queue for onsite visit dates requested by adopters, plus the onsite
 * payment / pet-turnover workflow for confirmed dates.
 *
 * Confirming or rejecting a requested date is a decision about the *date*
 * only — the adoption application keeps its own (approved) status, so a
 * rejected date never rejects the application.
 */
export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending_confirmation');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busyId, setBusyId] = useState('');
  const [rejectingId, setRejectingId] = useState('');
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');

  // Payment / turnover summaries, keyed by application id. Only loaded for
  // confirmed appointments (the ones with an onsite transaction to run).
  const [summaries, setSummaries] = useState<Record<string, PaymentSummary>>({});
  const [summaryErrors, setSummaryErrors] = useState<Record<string, boolean>>({});

  const loadSummaries = (items: Appointment[]) => {
    const appIds = items
      .filter((a) => a.status === 'confirmed')
      .map((a) => a.application);
    // Discard stale summaries while fresh requests are in flight.
    setSummaries({});
    setSummaryErrors({});
    if (appIds.length === 0) return;
    Promise.all(
      appIds.map((appId) =>
        applicationService
          .paymentSummary(appId)
          .then((summaryRes) => ({ appId, ok: true, summary: summaryRes.data as PaymentSummary }))
          .catch(() => ({ appId, ok: false, summary: null as PaymentSummary | null })),
      ),
    ).then((results) => {
      const nextSummaries: Record<string, PaymentSummary> = {};
      const nextErrors: Record<string, boolean> = {};
      for (const result of results) {
        if (result.ok && result.summary) {
          nextSummaries[result.appId] = result.summary;
        } else {
          nextErrors[result.appId] = true;
        }
      }
      setSummaries(nextSummaries);
      setSummaryErrors(nextErrors);
    });
  };
const load = () => {
    setLoading(true);
    setError('');
    appointmentService
      .list(statusFilter ? { status: statusFilter } : {})
      .then((res) => {
        const items = res.data.results as Appointment[];
        setAppointments(items);
        loadSummaries(items);
      })
      .catch(() => setError('Failed to load appointment requests.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter]);

  /** Re-fetch one application's payment summary after a payment is recorded. */
  const refreshSummary = (applicationId: string) => {
    setSummaryErrors((prev) => {
      const next = { ...prev };
      delete next[applicationId];
      return next;
    });
    applicationService
      .paymentSummary(applicationId)
      .then((res) => {
        const summary = res.data as PaymentSummary;
        setSummaries((prev) => ({ ...prev, [applicationId]: summary }));
      })
      .catch(() => setSummaryErrors((prev) => ({ ...prev, [applicationId]: true })));
  };

  const handleTurnoverCompleted = () => {
    setSuccess('Pet turnover confirmed and the adoption is now completed.');
    load();
  };

  const handleApprove = (appointment: Appointment) => {
    setBusyId(appointment.id);
    setError('');
    setSuccess('');
    appointmentService
      .approve(appointment.id)
      .then(() => {
        setSuccess(
          `Visit date confirmed for ${appointment.adopter_email}. The adoption record is now scheduled.`,
        );
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        setError(data?.error || data?.detail || 'Failed to confirm the appointment date.');
      })
      .finally(() => setBusyId(''));
  };
const handleReject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setReasonError('A reason is required when rejecting a date.');
      return;
    }
    setBusyId(rejectingId);
    setError('');
    setSuccess('');
    appointmentService
      .reject(rejectingId, reason.trim())
      .then(() => {
        setSuccess('Requested date rejected. The adopter can choose another date.');
        setRejectingId('');
        setReason('');
        setReasonError('');
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        setError(data?.error || data?.detail || 'Failed to reject the appointment date.');
      })
      .finally(() => setBusyId(''));
  };

  return (
    <div>
      <PageHeader
        title="Appointments"
        subtitle="Adopters with an approved application choose an onsite visit date. Confirm or reject the requested date here — this does not change the application's own status. Once a date is confirmed, record the onsite payment and confirm pet turnover from this page."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.value || 'all'}
            onClick={() => setStatusFilter(filter.value)}
            className={`px-3 py-1.5 rounded-md text-sm border ${
              statusFilter === filter.value
                ? 'bg-primary-600 text-white border-primary-600'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {success && <p className="mb-4 text-sm text-green-600">{success}</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {loading ? (
        <Loading />
      ) : appointments.length === 0 ? (
        <Card>
          <Empty message="No appointment requests for this filter." />
        </Card>
      ) : (
        <div className="space-y-4">
          {appointments.map((appointment) => (
            <Card key={appointment.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {appointment.pet_name} — {appointment.adopter_email}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Requested visit date:{' '}
                    <span className="font-medium">{formatDate(appointment.requested_date)}</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Application {appointment.application} · Requested{' '}
                    {formatDate(appointment.created_at)}
                  </p>
                  {appointment.status === 'rejected' && appointment.rejection_reason && (
                    <p className="mt-2 text-sm text-red-700">
                      Rejection reason: {appointment.rejection_reason}
                    </p>
                  )}
                </div>
                <StatusBadge status={appointment.status} />
              </div>

              {appointment.status === 'confirmed' && (
                <OnsiteTransactionPanel
                  appointment={appointment}
                  summary={summaries[appointment.application]}
                  summaryError={summaryErrors[appointment.application] || false}
                  onPaymentRecorded={refreshSummary}
                  onTurnoverCompleted={handleTurnoverCompleted}
                  onRetrySummary={refreshSummary}
                />
              )}

              {appointment.status === 'pending_confirmation' && (
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Button
                    onClick={() => handleApprove(appointment)}
                    disabled={busyId === appointment.id}
                  >
                    Confirm Date
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setRejectingId(rejectingId === appointment.id ? '' : appointment.id);
                      setReason('');
                      setReasonError('');
                    }}
                    disabled={busyId === appointment.id}
                  >
                    {rejectingId === appointment.id ? 'Cancel' : 'Reject Date'}
                  </Button>
                </div>
              )}

              {rejectingId === appointment.id && (
                <form onSubmit={handleReject} className="mt-4 max-w-xl space-y-3">
                  <label className="block">
                    <span className="field-label mb-1">
                      Reason for rejecting the date <span className="text-red-600">(required)</span>
                    </span>
                    <textarea
                      value={reason}
                      onChange={(e) => {
                        setReason(e.target.value);
                        setReasonError('');
                      }}
                      rows={3}
                      placeholder="The adopter will see this reason and can choose another date."
                      className="field-input"
                    />
                  </label>
                  {reasonError && <p className="text-sm text-red-600">{reasonError}</p>}
                  <Button type="submit" variant="danger" disabled={busyId === appointment.id}>
                    {busyId === appointment.id ? 'Saving...' : 'Reject Requested Date'}
                  </Button>
                </form>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
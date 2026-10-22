import { useEffect, useState } from 'react';
import {
  Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select, Input, Textarea,
} from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { paymentService, appointmentService, applicationService } from '../services/apiService';
import type { Payment, PaginatedResponse, Appointment, PaymentSummary } from '../types';
import { formatDate, formatDateTime, formatCurrency } from '../utils/format';

/** Matches Payment.Status.choices in backend/apps/payments/models.py. */
const PAYMENT_STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'cancelled', label: 'Cancelled' },
];

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'gcash', label: 'GCash' },
  { value: 'paymaya', label: 'PayMaya' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'online', label: 'Online' },
];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function humanise(value: string): string {
  return value.replace(/_/g, ' ');
}

function shortId(value: string): string {
  return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}

function reportFilename(): string {
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `pawconnect-payment-records-${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.pdf`;
}

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

/**
 * Payment Records — single staff destination for recording onsite payments and viewing payment history.
 */
export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [appInput, setAppInput] = useState('');
  const [appFilter, setAppFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // ----- Onsite Payment Form State -----
  const [showRecordModal, setShowRecordModal] = useState(false);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loadingAppointments, setLoadingAppointments] = useState(false);
  const [selectedAppointmentId, setSelectedAppointmentId] = useState('');
  const [selectedSummary, setSelectedSummary] = useState<PaymentSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [payReference, setPayReference] = useState('');
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payNotes, setPayNotes] = useState('');
  const [payReceived, setPayReceived] = useState(false);
  const [submittingPayment, setSubmittingPayment] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    const params: Record<string, unknown> = { page };
    if (statusFilter) params.status = statusFilter;
    if (appFilter) params.application = appFilter;
    paymentService
      .list(params)
      .then((res) => {
        const data = res.data as PaginatedResponse<Payment>;
        setPayments(data.results);
        setCount(data.count);
        setHasPrevious(Boolean(data.previous));
        setHasNext(Boolean(data.next));
      })
      .catch(() => setError('Failed to load payment records.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [page, statusFilter, appFilter]);

  const loadConfirmedAppointments = () => {
    setLoadingAppointments(true);
    appointmentService
      .list({ status: 'confirmed' })
      .then((res) => {
        const items = res.data.results as Appointment[];
        setAppointments(items);
        if (items.length > 0 && !selectedAppointmentId) {
          setSelectedAppointmentId(items[0].id);
        }
      })
      .catch(() => {
        setFormError('Failed to load confirmed appointments.');
      })
      .finally(() => setLoadingAppointments(false));
  };

  useEffect(() => {
    if (showRecordModal) {
      loadConfirmedAppointments();
    }
  }, [showRecordModal]);

  // When selected appointment changes, load its payment summary
  useEffect(() => {
    if (!selectedAppointmentId) {
      setSelectedSummary(null);
      return;
    }
    const appt = appointments.find((a) => a.id === selectedAppointmentId);
    if (!appt) return;

    setLoadingSummary(true);
    setFormError('');
    applicationService
      .paymentSummary(appt.application)
      .then((res) => {
        const summary = res.data as PaymentSummary;
        setSelectedSummary(summary);
        const fee = Number(summary.adoption_fee || '500');
        const paid = Number(summary.total_paid || '0');
        const balance = Math.max(fee - paid, 0);
        // Default to remaining balance if > 0, otherwise full fee
        setPayAmount(balance > 0 ? String(balance) : String(fee));
      })
      .catch(() => {
        setSelectedSummary(null);
        setPayAmount('500.00');
      })
      .finally(() => setLoadingSummary(false));
  }, [selectedAppointmentId, appointments]);

  const handleRecordPaymentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');

    const appt = appointments.find((a) => a.id === selectedAppointmentId);
    if (!appt) {
      setFormError('Please select a confirmed appointment.');
      return;
    }

    const val = Number(payAmount);
    if (!payAmount || !Number.isFinite(val) || val <= 0) {
      setFormError('Enter a valid payment amount greater than zero.');
      return;
    }

    if (!payReceived) {
      setFormError('You must confirm that the payment has actually been received onsite.');
      return;
    }

    setSubmittingPayment(true);
    paymentService
      .recordOnsite({
        application: appt.application,
        amount: payAmount,
        method: payMethod,
        payment_date: payDate || undefined,
        reference_number: payReference.trim(),
        notes: payNotes.trim(),
        payment_received: true,
      })
      .then((res: { data: { receipt_number?: string } }) => {
        const rcpt = res.data.receipt_number;
        setFormSuccess(
          `Payment of ${formatCurrency(val)} recorded successfully` +
            (rcpt ? ` · Receipt ID: ${rcpt}` : '') +
            '. Note: Recording the payment does not complete the adoption.',
        );
        setPayReceived(false);
        setPayNotes('');
        setPayReference('');
        load();
        // Refresh summary for this appointment
        applicationService.paymentSummary(appt.application).then((res2) => {
          setSelectedSummary(res2.data as PaymentSummary);
        });
      })
      .catch((err: unknown) => {
        setFormError(readError(err, 'Failed to record onsite payment.'));
      })
      .finally(() => setSubmittingPayment(false));
  };

  const appInputValue = appInput.trim();
  const appInputInvalid = appInputValue !== '' && !UUID_PATTERN.test(appInputValue);

  const applyApplicationFilter = () => {
    if (appInputInvalid) {
      setError('Enter a valid application ID (UUID) or leave the field empty.');
      return;
    }
    setError('');
    setAppFilter(appInputValue);
    setPage(1);
  };

  const clearFilters = () => {
    setStatusFilter('');
    setAppFilter('');
    setAppInput('');
    setError('');
    setExportError('');
    setPage(1);
  };

  const exportPdf = () => {
    setExporting(true);
    setExportError('');
    setError('');
    const params: Record<string, unknown> = {};
    if (statusFilter) params.status = statusFilter;
    if (appFilter) params.application = appFilter;
    paymentService
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

  const downloadReceipt = (pay: Payment) => {
    setDownloadingId(pay.id);
    setExportError('');
    paymentService
      .receiptPdf(pay.id)
      .then((res) => {
        const blob = res.data as Blob;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        const refSlug = pay.receipt_number || pay.reference_number || pay.id.slice(0, 8);
        anchor.download = `pawconnect-receipt-${refSlug}.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      })
      .catch(() => {
        setExportError('Failed to download receipt PDF.');
      })
      .finally(() => setDownloadingId(null));
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <PageHeader
          title="Payment Records"
          subtitle="Single staff destination for recording onsite payments and viewing payment history. Recording a payment requires actual money receipt confirmation and does not complete the adoption."
        />
        <Button
          onClick={() => {
            setShowRecordModal(!showRecordModal);
            setFormError('');
            setFormSuccess('');
          }}
          variant={showRecordModal ? 'outline' : 'primary'}
        >
          {showRecordModal ? 'Close Payment Entry' : '+ Record Onsite Payment'}
        </Button>
      </div>

      {showRecordModal && (
        <Card className="mb-6 p-6 border-2 border-primary-200 bg-primary-50/20">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
            <div>
              <h3 className="text-lg font-bold text-slate-900">Record Onsite Payment</h3>
              <p className="text-xs text-slate-500">
                Record an onsite payment for an approved application with a confirmed visit appointment.
              </p>
            </div>
          </div>

          {formSuccess && (
            <div
              role="status"
              className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
            >
              {formSuccess}
            </div>
          )}

          {formError && (
            <div role="alert" className="mb-4 text-sm text-red-600 font-medium">
              {formError}
            </div>
          )}

          {loadingAppointments ? (
            <Loading label="Loading confirmed appointments..." />
          ) : appointments.length === 0 ? (
            <p className="text-sm text-slate-600">
              No confirmed appointments currently eligible for onsite payment. Only applications with confirmed visit dates appear here.
            </p>
          ) : (
            <form onSubmit={handleRecordPaymentSubmit} className="space-y-4 max-w-2xl">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Eligible Confirmed Appointment
                </label>
                <select
                  value={selectedAppointmentId}
                  onChange={(e) => setSelectedAppointmentId(e.target.value)}
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  {appointments.map((appt) => (
                    <option key={appt.id} value={appt.id}>
                      {appt.pet_name} — {appt.adopter_email} (Visit: {formatDate(appt.requested_date)})
                    </option>
                  ))}
                </select>
              </div>

              {loadingSummary ? (
                <Loading label="Loading payment balance..." />
              ) : selectedSummary && (
                <div className="rounded-md border border-slate-200 bg-white p-3">
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500">Adoption Fee:</span>
                      <p className="font-semibold text-slate-900">{formatCurrency(selectedSummary.adoption_fee)}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Total Paid:</span>
                      <p className="font-semibold text-slate-900">{formatCurrency(selectedSummary.total_paid)}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Remaining Balance:</span>
                      <p className={`font-semibold ${Number(selectedSummary.adoption_fee) - Number(selectedSummary.total_paid) > 0 ? 'text-red-700' : 'text-slate-900'}`}>
                        {formatCurrency(Math.max(Number(selectedSummary.adoption_fee) - Number(selectedSummary.total_paid), 0))}
                      </p>
                    </div>
                  </div>
                  {selectedSummary.is_fee_paid && (
                    <p className="mt-2 text-xs text-green-700 font-medium">
                      ✓ Required fee has already been reached for this application.
                    </p>
                  )}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="Amount Received (₱)"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={payAmount}
                  onChange={(e) => {
                    setPayAmount(e.target.value);
                    setFormError('');
                  }}
                  required
                />
                <Select
                  label="Payment Method"
                  value={payMethod}
                  onChange={(e) => setPayMethod(e.target.value)}
                  options={PAYMENT_METHODS}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="Payment Date"
                  type="date"
                  value={payDate}
                  onChange={(e) => setPayDate(e.target.value)}
                />
                <Input
                  label="Reference Number (optional)"
                  placeholder="e.g. OR / Check / Slip #"
                  value={payReference}
                  onChange={(e) => setPayReference(e.target.value)}
                />
              </div>

              <Textarea
                label="Notes (optional)"
                placeholder="e.g. Onsite cash payment received at front desk"
                rows={2}
                value={payNotes}
                onChange={(e) => setPayNotes(e.target.value)}
              />

              <div className="pt-2">
                <label className="inline-flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={payReceived}
                    onChange={(e) => {
                      setPayReceived(e.target.checked);
                      setFormError('');
                    }}
                    disabled={submittingPayment}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span>
                    I confirm that this payment has <strong>actually been received</strong> in full onsite.
                  </span>
                </label>
              </div>

              <div className="pt-2 flex items-center gap-3">
                <Button type="submit" disabled={submittingPayment || !payReceived}>
                  {submittingPayment ? 'Recording Payment…' : 'Record Payment & Generate Receipt'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowRecordModal(false)}
                  disabled={submittingPayment}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}

      <form
        className="mb-4 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          applyApplicationFilter();
        }}
      >
        <Select
          label="Status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          options={PAYMENT_STATUS_FILTERS}
        />
        <Input
          label="Application ID"
          value={appInput}
          onChange={(e) => setAppInput(e.target.value)}
          placeholder="Filter by application UUID"
        />
        <Button type="submit" variant="outline">
          Apply
        </Button>
        {(statusFilter || appFilter) && (
          <Button type="button" variant="outline" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
        <Button
          type="button"
          variant="secondary"
          onClick={exportPdf}
          disabled={exporting}
        >
          {exporting ? 'Preparing PDF…' : 'Export All Filtered PDF'}
        </Button>
      </form>
      {appInputInvalid && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          Enter a valid application ID (UUID) or leave the field empty.
        </p>
      )}
      {exportError && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          {exportError}
        </p>
      )}

      <p className="mb-2 text-xs text-slate-500">
        Status legend:{' '}
        {PAYMENT_STATUS_FILTERS
          .filter((opt) => opt.value)
          .map((opt) => <StatusBadge key={opt.value} status={opt.value} />)}
      </p>
      <p className="mb-4 text-xs text-slate-500">
        Only <span className="font-medium text-green-700">Completed</span> payments count as money
        received. Pending, failed, refunded, and cancelled records have not been received. Each
        transaction has an individual official PDF receipt download.
      </p>

      {loading ? (
        <Loading label="Loading payment records..." />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : payments.length === 0 ? (
        <Card>
          <Empty message="No payment records match these filters." />
        </Card>
      ) : (
        <>
          <Card>
            <Table
              headers={[
                'Receipt', 'Pet', 'Adopter', 'Application', 'Amount',
                'Method', 'Status', 'Payment date', 'Processed by', 'Action',
              ]}
            >
              {payments.map((pay) => (
                <tr key={pay.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                    {pay.receipt_number || pay.reference_number || '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">{pay.pet_name || '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {pay.adopter_email || pay.application}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500" title={pay.application}>
                    {shortId(pay.application_id || pay.application)}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-slate-900">
                    {formatCurrency(pay.amount)}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600 capitalize">
                    {humanise(pay.method)}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={pay.status} /></td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {pay.payment_date ? formatDate(pay.payment_date) : formatDateTime(pay.created_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">{pay.processed_by_email || '—'}</td>
                  <td className="px-4 py-3 text-sm">
                    <Button
                      variant="outline"
                      className="text-xs px-2.5 py-1"
                      onClick={() => downloadReceipt(pay)}
                      disabled={downloadingId === pay.id}
                    >
                      {downloadingId === pay.id ? 'PDF…' : 'Receipt PDF'}
                    </Button>
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
    </div>
  );
}

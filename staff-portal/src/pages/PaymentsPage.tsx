import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select, Input, Textarea } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { paymentService, applicationService } from '../services/apiService';
import type { Payment, Application } from '../types';
import { formatDate, formatDateTime } from '../utils/format';

/** Matches Payment.Method.choices in backend/apps/payments/models.py. */
const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'gcash', label: 'GCash' },
  { value: 'paymaya', label: 'PayMaya' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'online', label: 'Online' },
];

/** Matches Payment.Status.choices in backend/apps/payments/models.py. */
const PAYMENT_STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'cancelled', label: 'Cancelled' },
];

/** Fixed onsite adoption fee. */
const ADOPTION_FEE = '500.00';

function todayISO(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function humanise(value: string) {
  return value.replace(/_/g, ' ');
}

/**
 * Extract a user-friendly error message from a DRF error response.
 */
function extractErrorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data || typeof data !== 'object') return fallback;
  if (typeof data.error === 'string') return data.error;
  if (typeof data.detail === 'string') return data.detail;
  const messages: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (Array.isArray(val)) {
      const fieldLabel = key === 'non_field_errors' ? '' : `${humanise(key)}: `;
      messages.push(...val.map((v) => `${fieldLabel}${v}`));
    } else if (typeof val === 'string') {
      const fieldLabel = key === 'non_field_errors' ? '' : `${humanise(key)}: `;
      messages.push(`${fieldLabel}${val}`);
    }
  }
  return messages.length > 0 ? messages.join(' · ') : fallback;
}

const INITIAL_FORM = {
  application: '',
  amount: ADOPTION_FEE,
  method: 'cash',
  status: 'completed',
  payment_date: todayISO(),
  reference_number: '',
  notes: '',
};

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...INITIAL_FORM });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([paymentService.list(), applicationService.list()])
      .then(([payRes, appRes]) => {
        setPayments(payRes.data.results);
        setApps(appRes.data.results);
      })
      .catch(() => setError('Failed to load payments.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');

    if (!form.application) {
      setSubmitError('Select the application this payment belongs to.');
      return;
    }
    if (!form.amount || parseFloat(form.amount) <= 0) {
      setSubmitError('Enter a valid payment amount.');
      return;
    }

    setSubmitting(true);

    // Build payload — only include non-empty optional fields.
    const payload: Record<string, unknown> = {
      application: form.application,
      amount: form.amount,
      method: form.method,
      status: form.status,
    };
    if (form.payment_date) payload.payment_date = form.payment_date;
    if (form.reference_number.trim()) payload.reference_number = form.reference_number.trim();
    if (form.notes.trim()) payload.notes = form.notes.trim();

    paymentService
      .create(payload)
      .then(() => {
        setSuccess('Payment recorded successfully.');
        setShowForm(false);
        setForm({ ...INITIAL_FORM, payment_date: todayISO() });
        load();
      })
      .catch((err) => setSubmitError(extractErrorMessage(err, 'Failed to record payment.')))
      .finally(() => setSubmitting(false));
  };

  const handleStatusChange = (id: string, newStatus: string) => {
    paymentService
      .update(id, { status: newStatus })
      .then(() => {
        setSuccess('Payment status updated.');
        load();
      })
      .catch((err) => setError(extractErrorMessage(err, 'Failed to update payment status.')))
      .finally(() => {});
  };

  return (
    <div>
      <PageHeader title="Payments" subtitle="Record and manage onsite adoption payments" />
      <div className="mb-4">
        <Button onClick={() => { setShowForm(!showForm); setSubmitError(''); }}>
          {showForm ? 'Cancel' : 'Record Payment'}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-primary-900 mb-4">Record Onsite Payment</h3>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
            <Select
              label="Application"
              value={form.application}
              onChange={(e) => setForm({ ...form, application: e.target.value })}
              options={[
                { value: '', label: 'Select application' },
                ...apps.map((a) => ({
                  value: a.id,
                  label: `${a.pet_name} — ${a.adopter_email} (${humanise(a.status)})`,
                })),
              ]}
            />
            <Input
              label="Adoption Fee (₱)"
              type="number"
              step="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />
            <Select
              label="Payment Method"
              value={form.method}
              onChange={(e) => setForm({ ...form, method: e.target.value })}
              options={PAYMENT_METHODS}
            />
            <Select
              label="Payment Status"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              options={[
                { value: '', label: 'Select status' },
                ...PAYMENT_STATUSES,
              ]}
            />
            <Input
              label="Payment Date"
              type="date"
              value={form.payment_date}
              onChange={(e) => setForm({ ...form, payment_date: e.target.value })}
            />
            <Input
              label="Reference / OR No. (optional)"
              value={form.reference_number}
              onChange={(e) => setForm({ ...form, reference_number: e.target.value })}
              placeholder="e.g. OR-2026-0001"
            />
            <Textarea
              label="Staff Notes (optional)"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={3}
              placeholder="Internal notes about the onsite transaction"
            />
            {submitError && (
              <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                {submitError}
              </div>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Record Payment'}
            </Button>
          </form>
        </Card>
      )}

      {success && (
        <div role="status" className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {success}
        </div>
      )}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : payments.length === 0 ? (
        <Card><Empty message="No payments recorded." /></Card>
      ) : (
        <Card>
          <Table headers={['Application', 'Amount', 'Method', 'Status', 'Date', 'Reference', 'Actions']}>
            {payments.map((pay) => (
              <tr key={pay.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm text-slate-600">
                  {pay.adopter_email || pay.application}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-slate-900">
                  ₱{parseFloat(pay.amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600 capitalize">{humanise(pay.method)}</td>
                <td className="px-4 py-3"><StatusBadge status={pay.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {pay.payment_date ? formatDate(pay.payment_date) : formatDateTime(pay.created_at)}
                </td>
                <td className="px-4 py-3 text-sm text-slate-500">{pay.reference_number || '—'}</td>
                <td className="px-4 py-3">
                  <select
                    value={pay.status}
                    onChange={(e) => handleStatusChange(pay.id, e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                    aria-label={`Change status for payment ₱${pay.amount}`}
                  >
                    {PAYMENT_STATUSES.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

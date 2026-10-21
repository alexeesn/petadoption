import { useEffect, useState } from 'react';
import {
  Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select, Input,
} from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { paymentService } from '../services/apiService';
import type { Payment, PaginatedResponse } from '../types';
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

/** Rough UUID shape guard: the backend filters application_id as a UUID. */
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function humanise(value: string): string {
  return value.replace(/_/g, ' ');
}

function shortId(value: string): string {
  return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}

/**
 * Payment Records (read-only browsing).
 *
 * Payment creation happens inside the onsite schedule/application workflow
 * (Schedule and Application detail), not here. The backend list endpoint is
 * paginated (PageNumberPagination), so this page fetches one page at a time
 * and filters server-side (?status=, ?application=) instead of loading every
 * record into the browser. Payments are never edited or reassigned from this
 * page.
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
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        title="Payment Records"
        subtitle="Recorded adoption payments. Payments are recorded during the onsite workflow (Schedule or Application detail); this page is read-only."
      />

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
      </form>
      {appInputInvalid && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          Enter a valid application ID (UUID) or leave the field empty.
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
        received. Pending, failed, refunded, and cancelled records have not been received. Payments
        cannot be edited or reassigned from this page.
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
                'Method', 'Status', 'Payment date', 'Processed by',
              ]}
            >
              {payments.map((pay) => (
                <tr key={pay.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-medium text-slate-900">
                    {pay.receipt_number || '—'}
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
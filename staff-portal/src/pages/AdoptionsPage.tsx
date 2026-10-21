import { useEffect, useState } from 'react';
import {
  Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select,
} from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adoptionService } from '../services/apiService';
import type { AdoptionRecord, PaginatedResponse } from '../types';
import { formatDate, formatDateTime } from '../utils/format';

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

/**
 * Adoption Records (read-only browsing).
 *
 * Records are created server-side when staff confirm an onsite visit date; the
 * permanent transaction ID is generated and stored by the backend only when a
 * record is completed — never by this page. The list endpoint is paginated, so
 * the page fetches one page at a time and filters server-side (?status=) rather
 * than loading every record into the browser. No editing, deletion, or
 * completion actions exist here.
 */
export default function AdoptionsPage() {
  const [records, setRecords] = useState<AdoptionRecord[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  const clearFilters = () => {
    setStatusFilter('');
    setPage(1);
  };

  return (
<div>
      <PageHeader
        title="Adoption Records"
        subtitle="Created automatically by the backend when staff confirm an onsite visit date. This page is read-only — adoption status is managed through the Schedule and Application workflows."
      />

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
      </div>

      <p className="mb-2 text-xs text-slate-500">
        Status legend:{' '}
        {STATUS_FILTERS.filter((opt) => opt.value).map((opt) => (
          <StatusBadge key={opt.value} status={opt.value} />
        ))}
      </p>
      <p className="mb-4 text-xs text-slate-500">
        Only records with status <span className="font-medium text-green-700">Completed</span> are
        finalized adoptions — they carry a permanent transaction ID and the completion time and
        staff. Scheduled, cancelled, and returned records are not finalized. Nothing on this page
        can be edited.
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
                'Completed', 'Completed by', 'Appointment',
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
                  <td className="px-4 py-3"><StatusBadge status={rec.status} /></td>
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
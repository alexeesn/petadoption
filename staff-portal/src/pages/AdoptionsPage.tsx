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

/** Filename convention for the generated report: pawconnect-adoption-records-YYYY-MM-DD.pdf */
function reportFilename(): string {
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `pawconnect-adoption-records-${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.pdf`;
}

/**
 * Adoption Records (browsing and individual PDF download).
 *
 * Records are created server-side when staff confirm an onsite visit date; the
 * permanent transaction ID is generated and stored by the backend only when a
 * record is completed. Completed adoptions have individual PDF certificate downloads.
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
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

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

  /** Download an individual PDF for a single completed adoption */
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
        anchor.download = `pawconnect-adoption-${refSlug}.pdf`;
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
        subtitle="Persisted adoption records. Each completed adoption has an individual official PDF download. Use Export All Filtered PDF for aggregate records."
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
        Only records with status <span className="font-medium text-green-700">Completed</span> are
        finalized adoptions — they carry a permanent transaction ID and can be downloaded as an individual official PDF.
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
                  <td className="px-4 py-3 text-sm">
                    {rec.status === 'completed' ? (
                      <Button
                        variant="outline"
                        className="text-xs px-2.5 py-1"
                        onClick={() => downloadRecordPdf(rec)}
                        disabled={downloadingId === rec.id}
                      >
                        {downloadingId === rec.id ? 'PDF…' : 'Download PDF'}
                      </Button>
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
    </div>
  );
}

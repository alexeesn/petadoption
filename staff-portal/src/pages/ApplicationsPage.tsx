import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { applicationService } from '../services/apiService';
import type { Application } from '../types';
import { RecordScopeTabs } from '../components/RecordScopeTabs';
import { useRecordFilters } from '../hooks/useRecordFilters';

const STATUSES = [
  ['draft', 'Draft'], ['submitted', 'Submitted'], ['under_review', 'Under Review'],
  ['pending_documents', 'Pending Documents'], ['additional_info_requested', 'Additional Info Requested'],
  ['approved', 'Approved'], ['rejected', 'Rejected'], ['cancelled', 'Cancelled'],
  ['adoption_completed', 'Adoption Completed'],
];
const HISTORY_STATUSES = ['rejected', 'cancelled', 'adoption_completed'];

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { scope, page, statusFilter, setScope, setPage, setStatusFilter } = useRecordFilters();
  const [pagination, setPagination] = useState({ count: 0, next: false, previous: false });

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    const params = { scope, page, ...(statusFilter ? { status: statusFilter } : {}) };
    applicationService
      .list(params)
      .then(({ data }) => {
        if (!active) return;
        setApps(data.results);
        setPagination({ count: data.count, next: !!data.next, previous: !!data.previous });
      })
      .catch(() => { if (active) setError('Failed to load applications.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [scope, page, statusFilter]);

  return (
    <div>
      <PageHeader title="Applications" subtitle="Review and manage adoption applications" />
      <RecordScopeTabs scope={scope} onChange={setScope} />
      <p className="mb-4 text-sm text-stone-600">Ongoing applications are in Active. Completed, rejected and cancelled applications remain in History.</p>
      <div className="mb-4">
        <label htmlFor="application-status" className="field-label mb-1">Filter by status</label>
        <select
          id="application-status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="field-input w-auto"
        >
          <option value="">All statuses</option>
          {STATUSES.filter(([value]) => scope === 'all' || HISTORY_STATUSES.includes(value) === (scope === 'history'))
            .map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : apps.length === 0 ? (
        <Card><Empty message="No applications found." /></Card>
      ) : (
        <Card>
          <Table headers={['Applicant', 'Pet', 'Status', 'Submitted', '']}>
            {apps.map((app) => (
              <tr key={app.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm">
                  <span className="font-medium text-slate-900">
                    {app.adopter_name || app.adopter_email}
                  </span>
                  {app.adopter_name && (
                    <span className="block text-xs text-slate-500">{app.adopter_email}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{app.pet_name}</td>
                <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {new Date(app.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/applications/${app.id}`}
                    className="text-primary-600 hover:underline text-sm font-medium"
                  >
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
      {!error && pagination.count > 0 && <nav aria-label="Application pages" className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={loading || !pagination.previous} onClick={() => setPage(page - 1)}>Previous</Button>
        <span className="text-sm text-stone-600">Page {page} · {pagination.count} applications</span>
        <Button variant="outline" disabled={loading || !pagination.next} onClick={() => setPage(page + 1)}>Next</Button>
      </nav>}
    </div>
  );
}

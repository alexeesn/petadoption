import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { applicationService } from '../services/apiService';
import type { Application } from '../types';

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    const params = statusFilter ? { status: statusFilter } : {};
    applicationService
      .list(params)
      .then((res) => setApps(res.data.results))
      .catch(() => setError('Failed to load applications.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter]);

  return (
    <div>
      <PageHeader title="Applications" subtitle="Review and manage adoption applications" />
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-1">Filter by status</label>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="under_review">Under Review</option>
          <option value="pending_documents">Pending Documents</option>
          <option value="additional_info_requested">Additional Info Requested</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="cancelled">Cancelled</option>
          <option value="adoption_completed">Adoption Completed</option>
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
          <Table headers={['Pet', 'Adopter', 'Status', 'Submitted', '']}>
            {apps.map((app) => (
              <tr key={app.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{app.pet_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{app.adopter_email}</td>
                <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {new Date(app.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/applications/${app.id}`}
                    className="text-indigo-600 hover:underline text-sm font-medium"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

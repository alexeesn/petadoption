import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Loading, ErrorMessage, Empty, Table, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adopterService } from '../services/apiService';
import type { AdopterProfile } from '../types';
import { formatDisplayName } from '../utils/format';

export default function AdoptersPage() {
  const [adopters, setAdopters] = useState<AdopterProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    adopterService
      .list()
      .then((res) => setAdopters(res.data.results))
      .catch(() => setError('Failed to load adopters.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader title="Adopters" subtitle="View registered adopters and their profiles" />
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : adopters.length === 0 ? (
        <Card><Empty message="No adopters found." /></Card>
      ) : (
        <Card>
          <Table headers={['Name', 'Email', 'Location', 'Verification', 'Joined', 'Actions']}>
            {adopters.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{formatDisplayName(a.user_name)}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{a.user_email}</td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {[formatDisplayName(a.city), formatDisplayName(a.state)].filter(Boolean).join(', ') || '—'}
                </td>
                <td className="px-4 py-3 text-sm">
                  <StatusBadge status={a.identity_verification_status || 'not_submitted'} />
                </td>
                <td className="px-4 py-3 text-sm text-slate-500">{new Date(a.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-sm">
                  <Link
                    to="/verification-requests"
                    className="text-xs font-semibold text-primary-600 hover:text-primary-800 hover:underline uppercase tracking-wide"
                  >
                    View Verification
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

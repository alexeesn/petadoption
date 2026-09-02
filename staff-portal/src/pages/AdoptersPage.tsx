import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adopterService } from '../services/apiService';
import type { AdopterProfile } from '../types';

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
          <Table headers={['Name', 'Email', 'City', 'State', 'Joined']}>
            {adopters.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{a.user_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{a.user_email}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{a.city}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{a.state}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{new Date(a.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

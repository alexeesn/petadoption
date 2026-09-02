import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Loading, ErrorMessage, StatusBadge, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { getDashboardStats } from '../services/apiService';

interface Stats {
  totalApplications: number;
  totalPets: number;
  totalAdopters: number;
  totalAdoptions: number;
  recentApplications: Array<{
    id: string;
    pet_name: string;
    adopter_email: string;
    status: string;
    created_at: string;
  }>;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getDashboardStats()
      .then((data) => setStats(data))
      .catch(() => setError('Failed to load dashboard statistics.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading dashboard..." />;
  if (error) return <ErrorMessage message={error} />;
  if (!stats) return null;

  const cards = [
    { label: 'Applications', value: stats.totalApplications, to: '/applications' },
    { label: 'Pets', value: stats.totalPets, to: '/pets' },
    { label: 'Adopters', value: stats.totalAdopters, to: '/adopters' },
    { label: 'Adoption Records', value: stats.totalAdoptions, to: '/adoptions' },
  ];

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Overview of adoption operations" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((c) => (
          <Link key={c.label} to={c.to}>
            <Card className="p-5 hover:shadow-md transition-shadow">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className="text-3xl font-bold text-slate-900 mt-1">{c.value}</p>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <div className="px-5 py-4 border-b border-slate-200">
          <h3 className="font-semibold text-slate-900">Recent Applications</h3>
        </div>
        {stats.recentApplications.length === 0 ? (
          <p className="p-5 text-sm text-slate-500">No applications yet.</p>
        ) : (
          <Table headers={['Pet', 'Adopter', 'Status', 'Submitted']}>
            {stats.recentApplications.map((app) => (
              <tr key={app.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">
                  <Link to={`/applications/${app.id}`} className="text-indigo-600 hover:underline">
                    {app.pet_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{app.adopter_email}</td>
                <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {new Date(app.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

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

      <Card className="mb-8 overflow-hidden">
        <div className="grid grid-cols-2 divide-stone-200 lg:grid-cols-4 lg:divide-x">
          {cards.map((c, i) => (
            <Link
              key={c.label}
              to={c.to}
              className={`group block px-6 py-5 transition-colors hover:bg-primary-50/60 ${
                i % 2 === 1 ? 'border-l border-stone-200 lg:border-l-0' : ''
              } ${i > 1 ? 'border-t border-stone-200 lg:border-t-0' : ''}`}
            >
              <p className="text-sm font-medium text-stone-600">{c.label}</p>
              <p className="mt-2 font-display text-5xl font-extrabold tabular-nums text-primary-900">{c.value}</p>
              <span className="mt-3 block h-1 w-8 rounded-full bg-accent-400 transition-all group-hover:w-14" aria-hidden="true" />
            </Link>
          ))}
        </div>
      </Card>

      <Card>
        <div className="border-b border-stone-200 px-6 py-4">
          <h3 className="text-lg font-bold text-primary-900">Recent Applications</h3>
        </div>
        {stats.recentApplications.length === 0 ? (
          <p className="p-6 text-sm text-stone-500">No applications yet.</p>
        ) : (
          <Table headers={['Pet', 'Adopter', 'Status', 'Submitted']}>
            {stats.recentApplications.map((app) => (
              <tr key={app.id} className="transition-colors hover:bg-stone-50">
                <td className="px-6 py-4 text-sm font-semibold text-primary-700">
                  <Link to={`/applications/${app.id}`} className="hover:underline">
                    {app.pet_name}
                  </Link>
                </td>
                <td className="px-6 py-4 text-sm text-stone-600">{app.adopter_email}</td>
                <td className="px-6 py-4"><StatusBadge status={app.status} /></td>
                <td className="px-6 py-4 text-sm text-stone-500">
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

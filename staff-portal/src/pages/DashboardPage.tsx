import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Loading, ErrorMessage, StatusBadge, Table } from '../components/UI';
import { Icon } from '../components/Icons';
import { PageHeader } from '../layouts/DashboardLayout';
import { getDashboardStats } from '../services/apiService';

type Stats = Awaited<ReturnType<typeof getDashboardStats>>;

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
    { label: 'Available Pets', value: stats.available_pets, to: '/pets?scope=active&status=available', icon: 'paw' },
    { label: 'Active Applications', value: stats.active_applications, to: '/applications?scope=active', icon: 'clipboard' },
    { label: 'Scheduled Adoptions', value: stats.scheduled_adoptions, to: '/adoptions?scope=active', icon: 'calendar' },
    { label: 'Completed Adoptions', value: stats.completed_adoptions, to: '/adoptions?scope=history&status=completed', icon: 'home' },
  ];

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Overview of adoption operations" />

      <div className="mb-7 grid grid-cols-2 gap-3 xl:grid-cols-4 sm:gap-5">
        {cards.map(c => <Link key={c.label} to={c.to} className="panel stat-card group min-w-0 p-4 transition-colors hover:border-primary-300 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-2"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary-100 bg-primary-50 text-primary-700"><Icon name={c.icon} className="h-[18px] w-[18px]" /></span><svg viewBox="0 0 24 24" className="h-4 w-4 text-stone-400" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" /></svg></div>
          <p className="text-3xl font-bold tracking-tight text-stone-900 tabular-nums sm:text-4xl">{c.value}</p>
          <p className="mt-2 text-xs font-medium text-stone-500 sm:text-sm">{c.label}</p>
        </Link>)}
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_17rem]"><Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-5 py-5">
          <div><h3 className="text-base font-bold text-stone-900">Recent Active Applications</h3><p className="mt-1 text-xs text-stone-500">Keep the next adoption moving. Finished applications are in History.</p></div><Link to="/applications" className="btn btn-outline">View applications</Link>
        </div>
        {stats.recent_applications.length === 0 ? (
          <p className="p-6 text-sm text-stone-500">No active applications.</p>
        ) : (
          <Table headers={['Pet', 'Adopter', 'Status', 'Submitted']}>
            {stats.recent_applications.map((app) => (
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
      <aside className="workspace-links" aria-label="Workspace shortcuts">
        <p className="section-label">Keep things moving</p>
        <h3 className="mt-2 text-base font-bold text-stone-900">Your workspace</h3>
        {[
          ['/applications', 'clipboard', 'Review applications', 'Help the next adoption take shape.'],
          ['/appointments', 'calendar', 'Manage appointments', 'Coordinate visits and reschedules.'],
          ['/pets', 'paw', 'Update pet profiles', 'Keep every story up to date.'],
        ].map(([to,icon,title,description]) => <Link key={to} to={to} className="workspace-link"><span className="workspace-link-icon"><Icon name={icon} className="h-4 w-4" /></span><span><span className="workspace-link-title">{title}</span><span className="mt-1 block text-xs leading-5 text-stone-500">{description}</span></span></Link>)}
      </aside></div>
    </div>
  );
}

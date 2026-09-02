import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { notificationService } from '../services/apiService';
import type { Notification } from '../types';

export default function NotificationsPage() {
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    notificationService
      .list()
      .then((res: { data: { results: Notification[] } }) => setNotifs(res.data.results))
      .catch(() => setError('Failed to load notifications.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader title="Notifications" subtitle="System notifications for staff" />
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : notifs.length === 0 ? (
        <Card><Empty message="No notifications found." /></Card>
      ) : (
        <Card>
          <Table headers={['Title', 'Message', 'Read', 'Created']}>
            {notifs.map((n) => (
              <tr key={n.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{n.title}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{n.message}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{n.is_read ? 'Yes' : 'No'}</td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {new Date(n.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

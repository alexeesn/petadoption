import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adoptionService } from '../services/apiService';
import type { AdoptionRecord } from '../types';
import { formatDate } from '../utils/format';

/**
 * Adoption Records are created by the backend when staff confirm an adoption
 * appointment (POST /api/appointments/<id>/approve/): the record arrives here
 * already "Scheduled" with its pet, adopter, application and visit date, so
 * nothing has to be entered by hand.  Staff only move the record on
 * (cancel/return here) or complete the adoption from the application page.
 */
const STATUS_OPTIONS = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'returned', label: 'Returned' },
];

export default function AdoptionsPage() {
  const [records, setRecords] = useState<AdoptionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busyId, setBusyId] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    adoptionService
      .list()
      .then((res) => setRecords(res.data.results))
      .catch(() => setError('Failed to load adoption records.'))
      .finally(() => setLoading(false));
  };

  const handleStatusChange = (id: string, status: string) => {
    setBusyId(id);
    setError('');
    setSuccess('');
    adoptionService
      .update(id, { status })
      .then(() => {
        setSuccess('Adoption status updated.');
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        setError(data?.error || data?.detail || 'Failed to update adoption status.');
      })
      .finally(() => setBusyId(''));
  };

  useEffect(load, []);

  return (
    <div>
      <PageHeader
        title="Adoption Records"
        subtitle="Scheduled automatically when staff confirm an adoption appointment — no manual record needed."
      />

      {success && <p className="mb-4 text-green-600 text-sm">{success}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : records.length === 0 ? (
        <Card><Empty message="No adoption records found." /></Card>
      ) : (
        <Card>
          <Table headers={['Pet', 'Adopter', 'Status', 'Application', 'Scheduled visit', 'Appointment', 'Completed', 'Update status']}>
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{rec.pet_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.adopter_email}</td>
                <td className="px-4 py-3"><StatusBadge status={rec.status} /></td>
                <td className="px-4 py-3 text-xs text-slate-500">{rec.application_id}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{formatDate(rec.adoption_date ?? undefined)}</td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {rec.appointment_id
                    ? `${formatDate(rec.appointment_date ?? undefined)} · ${rec.appointment_id}`
                    : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-500">{formatDate(rec.completed_date ?? undefined)}</td>
                <td className="px-4 py-3">
                  <select
                    value={rec.status}
                    onChange={(e) => handleStatusChange(rec.id, e.target.value)}
                    disabled={busyId === rec.id}
                    aria-label={`Update status for the adoption record of ${rec.pet_name}`}
                    className="rounded-md border border-slate-300 px-2 py-1 text-sm disabled:opacity-60"
                  >
                    {STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}


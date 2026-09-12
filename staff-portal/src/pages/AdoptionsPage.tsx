import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { adoptionService, applicationService } from '../services/apiService';
import type { AdoptionRecord, Application } from '../types';

const STATUS_OPTIONS = [
  { value: 'approved', label: 'Approved' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'returned', label: 'Returned' },
];

export default function AdoptionsPage() {
  const [records, setRecords] = useState<AdoptionRecord[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    application_id: '',
    scheduled_date: '',
    notes: '',
    cost: '0',
  });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([adoptionService.list(), applicationService.list({ status: 'approved' })])
      .then(([adoptRes, appRes]) => {
        setRecords(adoptRes.data.results);
        const existingAppIds = new Set(adoptRes.data.results.map((r: AdoptionRecord) => r.application));
        setApps(appRes.data.results.filter((a: Application) => !existingAppIds.has(a.id)));
      })
      .catch(() => setError('Failed to load adoption records.'))
      .finally(() => setLoading(false));
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    setSubmitting(true);
    adoptionService
      .create(form)
      .then(() => {
        setSuccess('Adoption record created.');
        setShowForm(false);
        setForm({ application_id: '', scheduled_date: '', notes: '', cost: '0' });
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        const msg = data?.application_id?.[0] || data?.error || data?.detail || 'Failed to create adoption record.';
        setSubmitError(Array.isArray(msg) ? msg.join(' ') : String(msg));
      })
      .finally(() => setSubmitting(false));
  };

  const handleStatusChange = (id: string, status: string) => {
    adoptionService
      .update(id, { status })
      .then(() => {
        setSuccess('Adoption status updated.');
        load();
      })
      .catch(() => setError('Failed to update adoption status.'))
      .finally(() => {});
  };

  useEffect(load, []);

  return (
    <div>
      <PageHeader title="Adoption Records" subtitle="Track adoption progress from approved application to completion" />
      <div className="mb-4">
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Create Adoption Record'}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-slate-900 mb-4">New Adoption Record</h3>
          <form onSubmit={handleCreate} className="space-y-4 max-w-lg">
            <Select
              label="Approved Application"
              value={form.application_id}
              onChange={(e) => setForm({ ...form, application_id: e.target.value })}
              options={[{ value: '', label: 'Select application' }, ...apps.map((a) => ({ value: a.id, label: `${a.pet_name} - ${a.adopter_email}` }))]}
            />
            <label className="block">
              <span className="block text-sm font-medium text-slate-700 mb-1">Scheduled Date</span>
              <input
                type="date"
                value={form.scheduled_date}
                onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block">
              <span className="block text-sm font-medium text-slate-700 mb-1">Cost</span>
              <input
                type="number"
                step="0.01"
                value={form.cost}
                onChange={(e) => setForm({ ...form, cost: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block">
              <span className="block text-sm font-medium text-slate-700 mb-1">Notes</span>
              <textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            {submitError && <p className="text-red-600 text-sm">{submitError}</p>}
            {apps.length === 0 && <p className="text-amber-600 text-sm">No approved applications available for adoption.</p>}
            <Button type="submit" disabled={submitting || apps.length === 0}>
              {submitting ? 'Creating...' : 'Create Record'}
            </Button>
          </form>
        </Card>
      )}

      {success && <p className="mb-4 text-green-600 text-sm">{success}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : records.length === 0 ? (
        <Card><Empty message="No adoption records found." /></Card>
      ) : (
        <Card>
          <Table headers={['Pet', 'Adopter', 'Status', 'Scheduled', 'Completed', 'Actions']}>
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{rec.pet_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.adopter_email}</td>
                <td className="px-4 py-3"><StatusBadge status={rec.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">{rec.scheduled_date || '—'}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{rec.completed_date || '—'}</td>
                <td className="px-4 py-3">
                  <select
                    value={rec.status}
                    onChange={(e) => handleStatusChange(rec.id, e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-sm"
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


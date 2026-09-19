import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table, Button, Input, Select, Textarea } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { healthService, petService } from '../services/apiService';
import type { HealthRecord, Pet } from '../types';

/** Extracts a readable message from a DRF validation error response. */
function describeSaveError(err: unknown): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data;
  if (data && typeof data === 'object') {
    const messages = Object.values(data as Record<string, unknown>).map((value) =>
      Array.isArray(value) ? value.map(String).join(' ') : String(value)
    );
    const joined = messages.join(' ').trim();
    if (joined) return joined;
  }
  return 'Failed to create health record.';
}

export default function HealthRecordsPage() {
  const [records, setRecords] = useState<HealthRecord[]>([]);
  const [pets, setPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const emptyForm = {
    pet: '',
    record_date: '',
    diagnosis: '',
    treatment: '',
    veterinarian_name: '',
    veterinary_clinic: '',
    next_checkup_date: '',
    notes: '',
  };
  const [form, setForm] = useState({ ...emptyForm });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([healthService.list(), petService.list()])
      .then(([recRes, petRes]) => {
        setRecords(recRes.data.results);
        setPets(petRes.data.results);
      })
      .catch(() => setError('Failed to load health records.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    setSubmitting(true);
    // The API treats a blank next check-up as "no value", so omit it instead
    // of sending an empty string the date field would reject.
    const { next_checkup_date, ...rest } = form;
    const payload: Record<string, unknown> = { ...rest };
    if (next_checkup_date) payload.next_checkup_date = next_checkup_date;
    healthService
      .create(payload)
      .then(() => {
        setSuccess('Health record created.');
        setShowForm(false);
        setForm({ ...emptyForm });
        load();
      })
      .catch((err: unknown) => setSubmitError(describeSaveError(err)))
      .finally(() => setSubmitting(false));
  };

  return (
    <div>
      <PageHeader title="Health Records" subtitle="Manage pet medical records and vaccinations" />
      <div className="mb-4">
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Add Health Record'}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-slate-900 mb-4">New Health Record</h3>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
            <Select
              label="Pet"
              value={form.pet}
              onChange={(e) => setForm({ ...form, pet: e.target.value })}
              options={[{ value: '', label: 'Select pet' }, ...pets.map((p) => ({ value: p.id, label: p.name }))]}
            />
            <Input
              label="Record Date"
              type="date"
              required
              value={form.record_date}
              onChange={(e) => setForm({ ...form, record_date: e.target.value })}
            />
            <Input
              label="Diagnosis"
              value={form.diagnosis}
              onChange={(e) => setForm({ ...form, diagnosis: e.target.value })}
            />
            <Textarea
              label="Treatment"
              value={form.treatment}
              onChange={(e) => setForm({ ...form, treatment: e.target.value })}
            />
            <Input
              label="Veterinarian Name"
              value={form.veterinarian_name}
              onChange={(e) => setForm({ ...form, veterinarian_name: e.target.value })}
            />
            <Input
              label="Veterinary Clinic"
              value={form.veterinary_clinic}
              onChange={(e) => setForm({ ...form, veterinary_clinic: e.target.value })}
            />
            <Input
              label="Next Checkup Date"
              type="date"
              value={form.next_checkup_date}
              onChange={(e) => setForm({ ...form, next_checkup_date: e.target.value })}
            />
            <Textarea
              label="Notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
            {submitError && <p className="text-red-600 text-sm">{submitError}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Record'}
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
        <Card><Empty message="No health records found." /></Card>
      ) : (
        <Card>
          <Table headers={['Pet', 'Record Date', 'Diagnosis', 'Veterinarian', 'Notes', 'Created']}>
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{rec.pet_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.record_date}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.diagnosis || '—'}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.veterinarian_name || '—'}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{rec.notes}</td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {rec.created_at ? new Date(rec.created_at).toLocaleDateString() : 'N/A'}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}


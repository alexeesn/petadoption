import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Input, Select, Textarea } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { healthService, petService } from '../services/apiService';
import type { HealthRecord, Pet } from '../types';

export default function HealthRecordsPage() {
  const [records, setRecords] = useState<HealthRecord[]>([]);
  const [pets, setPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    pet: '',
    record_type: 'checkup',
    date: '',
    vet_name: '',
    vet_contact: '',
    notes: '',
  });
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
    healthService
      .create(form)
      .then(() => {
        setSuccess('Health record created.');
        setShowForm(false);
        setForm({ pet: '', record_type: 'checkup', date: '', vet_name: '', vet_contact: '', notes: '' });
        load();
      })
      .catch(() => setSubmitError('Failed to create health record.'))
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
            <Select
              label="Record Type"
              value={form.record_type}
              onChange={(e) => setForm({ ...form, record_type: e.target.value })}
              options={[
                { value: 'checkup', label: 'Checkup' },
                { value: 'treatment', label: 'Treatment' },
                { value: 'surgery', label: 'Surgery' },
                { value: 'vaccination', label: 'Vaccination' },
                { value: 'other', label: 'Other' },
              ]}
            />
            <Input
              label="Date"
              type="date"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
            <Input
              label="Veterinarian Name"
              value={form.vet_name}
              onChange={(e) => setForm({ ...form, vet_name: e.target.value })}
            />
            <Input
              label="Veterinarian Contact"
              value={form.vet_contact}
              onChange={(e) => setForm({ ...form, vet_contact: e.target.value })}
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
          <Table headers={['Pet', 'Record Type', 'Date', 'Veterinarian', 'Notes', 'Created']}>
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{rec.pet_name}</td>
                <td className="px-4 py-3"><StatusBadge status={rec.record_type || 'other'} /></td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.date}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.vet_name}</td>
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


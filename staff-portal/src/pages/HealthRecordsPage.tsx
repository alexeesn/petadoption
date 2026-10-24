import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table, Button, Input, Textarea, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { healthService } from '../services/apiService';
import type { HealthRecord, Pet } from '../types';
import { formatPetLabel, philippineDate } from '../utils/format';
import { useToast } from '../context/ToastContext';
import { RecordScopeTabs } from '../components/RecordScopeTabs';
import { useRecordFilters } from '../hooks/useRecordFilters';

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

function recordToForm(record: HealthRecord) {
  return {
    pet: record.pet,
    record_date: record.record_date,
    diagnosis: record.diagnosis,
    treatment: record.treatment,
    veterinarian_name: record.veterinarian_name,
    veterinary_clinic: record.veterinary_clinic,
    next_checkup_date: record.next_checkup_date ?? '',
    notes: record.notes,
  };
}

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
  return 'Failed to save health record. Please try again.';
}

export default function HealthRecordsPage() {
  const toast = useToast();
  const [records, setRecords] = useState<HealthRecord[]>([]);
  const [pets, setPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<HealthRecord | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<HealthRecord | null>(null);
  const [loadingRecord, setLoadingRecord] = useState(false);
  const [recordError, setRecordError] = useState('');
  const [loadingPets, setLoadingPets] = useState(false);
  const [petError, setPetError] = useState('');
  const { scope, page, setScope, setPage } = useRecordFilters();
  const [hasNext, setHasNext] = useState(false);
  const [total, setTotal] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({ ...emptyForm });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');
  const today = philippineDate();
  const viewingRecord = selectedRecord !== null && editing === null;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    healthService.list({ page, scope })
      .then(({ data }) => {
        if (!active) return;
        setRecords(data.results);
        setHasNext(data.next !== null);
        setTotal(data.count);
      })
      .catch(() => { if (active) setError('Failed to load health records. Please retry.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, scope, refresh]);

  useEffect(() => {
    if (!showForm || editing) return;
    let active = true;
    setLoadingPets(true);
    setPetError('');
    healthService.selectablePets()
      .then((choices) => {
        if (!active) return;
        setPets(choices);
        setForm(current => ({ ...current, pet: choices.some(pet => pet.id === current.pet) ? current.pet : '' }));
      })
      .catch(() => { if (active) setPetError('Could not load pets. Please retry.'); })
      .finally(() => { if (active) setLoadingPets(false); });
    return () => { active = false; };
  }, [showForm, editing, refresh]);

  useEffect(() => {
    if (!showForm || editing || !form.pet) return;
    let active = true;
    setLoadingRecord(true);
    setRecordError('');
    healthService.list({ pet: form.pet })
      .then(({ data }) => {
        if (!active) return;
        const record = data.results[0] ?? null;
        setSelectedRecord(record);
        if (record) setForm(recordToForm(record));
      })
      .catch(() => { if (active) setRecordError('Could not check the saved health record. Retry before saving.'); })
      .finally(() => { if (active) setLoadingRecord(false); });
    return () => { active = false; };
  }, [showForm, editing, form.pet, refresh]);

  const openNew = () => {
    setScope('active');
    setEditing(null);
    setSelectedRecord(null);
    setLoadingRecord(false);
    setRecordError('');
    setForm({ ...emptyForm });
    setPets([]);
    setLoadingPets(true);
    setPetError('');
    setSubmitError('');
    setSuccess('');
    setShowForm(true);
    setRefresh(current => current + 1);
  };

  const openEdit = (record: HealthRecord) => {
    setEditing(record);
    setSelectedRecord(record);
    setLoadingRecord(false);
    setRecordError('');
    setForm(recordToForm(record));
    setSubmitError('');
    setSuccess('');
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    if (viewingRecord || loadingRecord || recordError) return;
    if (!form.pet) {
      setSubmitError('Select a pet.');
      return;
    }
    const currentDate = philippineDate();
    if (!form.record_date) {
      setSubmitError('Record date is required.');
      return;
    }
    if (form.record_date > currentDate) {
      setSubmitError('Record date cannot be in the future.');
      return;
    }
    if (form.next_checkup_date && form.next_checkup_date < currentDate) {
      setSubmitError('Next checkup date cannot be in the past.');
      return;
    }
    setSubmitting(true);
    // Null also clears an existing date when staff remove it during Edit.
    const payload = { ...form, next_checkup_date: form.next_checkup_date || null };
    const request = editing ? healthService.update(editing.id, payload) : healthService.create(payload);
    request
      .then(() => {
        setSuccess(editing ? 'Health record updated.' : 'Health record created.');
        toast.success(editing ? 'Health record updated' : 'Health record added', 'The medical details have been saved.');
        if (!editing) setPage(1);
        setShowForm(false);
        setEditing(null);
        setSelectedRecord(null);
        setForm({ ...emptyForm });
        setRefresh(current => current + 1);
      })
      .catch((err: unknown) => {
        setSubmitError(describeSaveError(err));
        if (!editing) setRefresh(current => current + 1);
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <div>
      <PageHeader title="Health Records" subtitle="Manage pet medical records and vaccinations" />
      <div className="mb-4">
        <Button onClick={openNew} disabled={submitting}>Add Health Record</Button>
      </div>
      <RecordScopeTabs scope={scope} onChange={value => {
        if (submitting) return;
        setShowForm(false);
        setEditing(null);
        setSelectedRecord(null);
        setForm({ ...emptyForm });
        setSuccess('');
        setScope(value);
      }} />
      <p className="mb-4 text-sm text-stone-600">Active shows medical records for pets in the center's current care, including returned pets awaiting assessment. Adopted and inactive pets' records remain in History.</p>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-primary-900 mb-4">{editing ? 'Edit Health Record' : viewingRecord ? 'Saved Health Record' : 'New Health Record'}</h3>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
            {editing ? (
              <div>
                <label htmlFor="health-record-pet" className="field-label mb-1.5">Pet</label>
                <input id="health-record-pet" className="field-input" value={formatPetLabel(editing.pet_name)} readOnly aria-describedby="health-pet-help" />
                <p id="health-pet-help" className="mt-2 text-xs text-stone-500">This record stays linked to this pet.</p>
              </div>
            ) : (
              <div>
                <label className="block">
                  <span className="field-label mb-1.5">Pet</span>
                  <select
                    className="field-input"
                    value={form.pet}
                    onChange={(e) => {
                      setForm({ ...emptyForm, pet: e.target.value });
                      setSelectedRecord(null);
                      setLoadingRecord(e.target.value !== '');
                      setRecordError('');
                      setSubmitError('');
                      setSuccess('');
                    }}
                    required
                    disabled={loadingPets || !!petError || submitting || pets.length === 0}
                    aria-describedby="health-pet-help"
                  >
                    <option value="">{loadingPets ? 'Loading pets...' : 'Select pet'}</option>
                    {pets.map(pet => <option key={pet.id} value={pet.id}>{formatPetLabel(pet.name)} ({pet.species})</option>)}
                  </select>
                </label>
                <p id="health-pet-help" className="mt-2 text-xs text-stone-500">Choose a pet in the center's current care. Adopted and inactive pets' records are in History. Saved records open read-only; choose Edit Health Record to make changes. Changing the pet clears unsaved entries.</p>
                {!loadingPets && !petError && pets.length === 0 && <p role="status" className="mt-2 text-sm text-stone-600">No pets are available.</p>}
                {petError && <div role="alert" className="mt-2 text-sm text-red-600">{petError} <button type="button" className="font-semibold underline" onClick={() => setRefresh(current => current + 1)}>Retry loading pets</button></div>}
              </div>
            )}
            {loadingRecord && <p role="status" className="text-sm text-stone-600">Checking saved health record...</p>}
            {recordError && <p role="alert" className="text-sm text-red-600">{recordError} <button type="button" className="underline" onClick={() => setRefresh(current => current + 1)}>Retry</button></p>}
            {viewingRecord && <p role="status" className="text-sm text-primary-800">Viewing the saved record for {formatPetLabel(selectedRecord.pet_name)}. These details stay unchanged until you choose Edit Health Record and Save Changes.</p>}
            <fieldset disabled={viewingRecord || loadingRecord || !!recordError || submitting} className="space-y-4">
            <Input
              label="Record Date"
              type="date"
              max={today}
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
              min={today}
              value={form.next_checkup_date}
              onChange={(e) => setForm({ ...form, next_checkup_date: e.target.value })}
            />
            <Textarea
              label="Notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
            </fieldset>
            {submitError && <p role="alert" className="text-red-600 text-sm">{submitError}</p>}
            <div className="flex flex-wrap gap-3 border-t border-stone-200 pt-4">
              {viewingRecord ? (
                <Button key="start-edit" type="button" onClick={() => openEdit(selectedRecord)}>
                  Edit Health Record
                </Button>
              ) : (
                <Button key="save-record" type="submit" disabled={submitting || loadingRecord || !!recordError || (!editing && (loadingPets || !!petError || pets.length === 0))}>
                  {submitting ? 'Saving...' : editing ? 'Save Changes' : 'Save Record'}
                </Button>
              )}
              <Button variant="outline" onClick={() => setShowForm(false)} disabled={submitting}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {success && <p role="status" className="mb-4 text-green-600 text-sm">{success}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <div><ErrorMessage message={error} /><Button variant="outline" onClick={() => setRefresh(current => current + 1)}>Retry health records</Button></div>
      ) : records.length === 0 ? (
        <Card><Empty message="No health records found." /></Card>
      ) : (
        <Card>
          <div className="space-y-4 p-4 md:hidden">
            {records.map(rec => (
              <article key={rec.id} className="rounded-lg border border-stone-200 p-4">
                <h3 className="font-semibold text-stone-900">{formatPetLabel(rec.pet_name)}</h3>
                <div className="mt-2"><StatusBadge status={rec.pet_status} /></div>
                <dl className="mt-3 space-y-2 text-sm text-stone-600">
                  <div><dt className="font-medium">Record Date</dt><dd>{rec.record_date}</dd></div>
                  <div><dt className="font-medium">Diagnosis</dt><dd className="break-words whitespace-pre-line">{rec.diagnosis || 'Not recorded'}</dd></div>
                  <div><dt className="font-medium">Veterinarian</dt><dd>{rec.veterinarian_name || 'Not recorded'}</dd></div>
                  <div><dt className="font-medium">Notes</dt><dd className="break-words whitespace-pre-line">{rec.notes || 'Not recorded'}</dd></div>
                </dl>
                <Button variant="outline" onClick={() => openEdit(rec)} disabled={submitting}>Edit</Button>
              </article>
            ))}
          </div>
          <div className="hidden md:block">
          <Table headers={['Pet', 'Pet Status', 'Record Date', 'Diagnosis', 'Veterinarian', 'Notes', 'Created', 'Actions']}>
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{formatPetLabel(rec.pet_name)}</td>
                <td className="px-4 py-3 text-sm"><StatusBadge status={rec.pet_status} /></td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.record_date}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.diagnosis || '—'}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{rec.veterinarian_name || '—'}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{rec.notes}</td>
                <td className="px-4 py-3 text-sm text-slate-500">
                  {rec.created_at ? new Date(rec.created_at).toLocaleDateString() : 'N/A'}
                </td>
                <td className="px-4 py-3 text-sm"><button type="button" onClick={() => openEdit(rec)} disabled={submitting} className="font-medium text-primary-600 hover:underline disabled:opacity-50">Edit</button></td>
              </tr>
            ))}
          </Table>
          </div>
        </Card>
      )}
      {!error && total > 0 && (
        <nav aria-label="Health record pages" className="mt-4 flex flex-wrap items-center justify-center gap-3">
          <Button variant="outline" onClick={() => setPage(page - 1)} disabled={loading || page === 1}>Previous</Button>
          <span className="text-sm text-stone-500">Page {page} · {total} records</span>
          <Button variant="outline" onClick={() => setPage(page + 1)} disabled={loading || !hasNext}>Next</Button>
        </nav>
      )}
    </div>
  );
}


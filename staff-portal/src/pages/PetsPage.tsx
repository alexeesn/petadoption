import { useEffect, useRef, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Button, Input, Select, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { petService } from '../services/apiService';
import { formatPetAge, formatPetLabel, philippineDate, formatDisplayName } from '../utils/format';
import { PawMark } from '../components/Icons';
import type { Pet, PetImage } from '../types';
import { useToast } from '../context/ToastContext';
import { RecordScopeTabs } from '../components/RecordScopeTabs';
import { useRecordFilters } from '../hooks/useRecordFilters';

const PET_STATUSES = ['available', 'pending', 'reserved', 'for_assessment', 'under_medical_care', 'adopted', 'inactive'];
const ACTIVE_PET_STATUSES = ['available', 'pending', 'reserved', 'for_assessment', 'under_medical_care'];
const CARE_STATUSES = [
  { value: 'for_assessment', label: 'For Assessment' },
  { value: 'under_medical_care', label: 'Under Medical Care' },
  { value: 'available', label: 'Available' },
];

const emptyForm = {
  name: '',
  status: 'available',
  species: 'dog',
  breed: '',
  age_years: '',
  age_months: '0',
  gender: 'unknown',
  weight_kg: '',
  color: '',
  description: '',
  arrival_date: '',
  is_vaccinated: false,
  is_neutered: false,
};

const MAX_AGE_YEARS = 40;
const MAX_AGE_MONTHS = 11;

/** Maps a pet record to the editable form fields. */
function petToForm(pet: Pet) {
  return {
    name: pet.name,
    status: pet.status,
    species: pet.species,
    breed: pet.breed,
    age_years: pet.age_years !== undefined && pet.age_years !== null ? String(pet.age_years) : '',
    age_months: pet.age_months !== undefined && pet.age_months !== null ? String(pet.age_months) : '0',
    gender: pet.gender,
    weight_kg: pet.weight_kg ?? '',
    color: pet.color,
    description: pet.description,
    arrival_date: pet.arrival_date ?? '',
    is_vaccinated: pet.is_vaccinated,
    is_neutered: pet.is_neutered,
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
  return 'Failed to save pet.';
}

export default function PetsPage() {
  const toast = useToast();
  const { scope, page, statusFilter, setScope, setPage, setStatusFilter } = useRecordFilters();
  const [pagination, setPagination] = useState({ count: 0, next: false, previous: false });
  const [refresh, setRefresh] = useState(0);
  const [pets, setPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Pet | null>(null);
  const [form, setForm] = useState({ ...emptyForm });

  // Every selected image is kept, so 2, 3, 4+ files can be uploaded at once.
  const [photos, setPhotos] = useState<{ file: File; url: string }[]>([]);
  // Photos already saved for the pet being edited, and the ones staff explicitly
  // marked for removal. An existing photo is only deleted through
  // `removedPhotos`, never because it was absent from a new file selection.
  const [existingPhotos, setExistingPhotos] = useState<PetImage[]>([]);
  const [removedPhotos, setRemovedPhotos] = useState<PetImage[]>([]);
  const [loadingPhotos, setLoadingPhotos] = useState(false);
  const [photoError, setPhotoError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [saving, setSaving] = useState(false);
  const photosRef = useRef(photos);
  photosRef.current = photos;

  // Release the blob URLs used for previews when the page unmounts.
  useEffect(
    () => () => {
      photosRef.current.forEach((p) => URL.revokeObjectURL(p.url));
    },
    []
  );

  const clearPhotos = () => {
    photosRef.current.forEach((p) => URL.revokeObjectURL(p.url));
    setPhotos([]);
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    petService
      .list({ scope, page, ...(statusFilter ? { status: statusFilter } : {}) })
      .then(({ data }) => {
        if (!active) return;
        setPets(data.results);
        setPagination({ count: data.count, next: !!data.next, previous: !!data.previous });
      })
      .catch(() => { if (active) setError('Failed to load pets.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [scope, page, statusFilter, refresh]);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    clearPhotos();
    setExistingPhotos([]);
    setRemovedPhotos([]);
    setPhotoError('');
    setSubmitError('');
    setShowForm(true);
  };

  // The list endpoint deliberately omits photos, so the full pet record is
  // fetched here to make every existing photo visible while editing.
  const openEdit = (pet: Pet) => {
    setEditing(pet);
    setForm(petToForm(pet));
    clearPhotos();
    setExistingPhotos([]);
    setRemovedPhotos([]);
    setPhotoError('');
    setSubmitError('');
    setShowForm(true);
    setLoadingPhotos(true);
    petService
      .retrieve(pet.id)
      .then((res) => {
        const detail = res.data as Pet;
        setEditing(detail);
        setForm(petToForm(detail));
        setExistingPhotos(detail.images ?? []);
      })
      .catch(() =>
        setPhotoError('Existing photos could not be loaded. Close and reopen Edit Pet to retry.')
      )
      .finally(() => setLoadingPhotos(false));
  };

  // Appends the newly picked files to the existing selection instead of
  // replacing it, so several file-picker actions add up: dog1 + dog2, then
  // dog3 + dog4 => all four stay selected until the pet is submitted.
  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPhotoError('');
    const files = Array.from(e.target.files ?? []);
    // Reset the input so selecting the same files again still fires change.
    e.target.value = '';
    const images = files.filter((f) => f.type.startsWith('image/'));
    const ignored = files.length - images.length;
    if (ignored > 0) {
      setPhotoError(
        `${ignored} non-image file${ignored > 1 ? 's were' : ' was'} ignored. Only image files are allowed.`
      );
    }
    const added = images.map((file) => ({ file, url: URL.createObjectURL(file) }));
    setPhotos([...photosRef.current, ...added]);
  };

  // Removes one selected photo before submission; only that preview URL is
  // released, the remaining selection is kept untouched.
  const removePhoto = (index: number) => {
    const target = photosRef.current[index];
    if (!target) return;
    URL.revokeObjectURL(target.url);
    setPhotos(photosRef.current.filter((_, i) => i !== index));
  };

  // Marks one saved photo for removal. It is deleted only when staff save, so
  // cancelling the form leaves the pet's photos exactly as they were.
  const markPhotoForRemoval = (photo: PetImage) => {
    setExistingPhotos((current) => current.filter((p) => p.id !== photo.id));
    setRemovedPhotos((current) => [...current, photo]);
  };

  const undoPhotoRemoval = (photo: PetImage) => {
    setRemovedPhotos((current) => current.filter((p) => p.id !== photo.id));
    setExistingPhotos((current) => [...current, photo]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    const ageYears = Number(form.age_years);
    if (form.age_years === '' || !Number.isInteger(ageYears) || ageYears < 0 || ageYears > MAX_AGE_YEARS) {
      setSubmitError(`Age (Years) must be a whole number between 0 and ${MAX_AGE_YEARS}.`);
      return;
    }
    const ageMonths = Number(form.age_months);
    if (form.age_months === '' || !Number.isInteger(ageMonths) || ageMonths < 0 || ageMonths > MAX_AGE_MONTHS) {
      setSubmitError(`Age (Months) must be a whole number between 0 and ${MAX_AGE_MONTHS}.`);
      return;
    }
    const weight = form.weight_kg.trim();
    if (weight !== '' && (!/^\d+(\.\d{1,2})?$/.test(weight) || Number(weight) < 0.01 || Number(weight) > 9999.99)) {
      setSubmitError('Weight must be between 0.01 and 9999.99 kg, with up to 2 decimal places.');
      return;
    }
    if (form.arrival_date && form.arrival_date > philippineDate()) {
      setSubmitError('Arrival date cannot be in the future.');
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        // 1. Update the pet information. Photos live on their own endpoint, so
        //    this request can never remove a photo.
        await petService.update(editing.id, {
          ...form,
          status: form.status !== editing.status ? form.status : undefined,
          weight_kg: weight || null,
          age_years: ageYears,
          age_months: ageMonths,
          arrival_date: form.arrival_date || null,
        });
        // 2. Delete only the photos staff explicitly marked for removal.
        for (const photo of removedPhotos) {
          await petService.removeImage(editing.id, photo.id);
        }
        // 3. Append the newly selected photos; existing photos stay attached.
        for (const { file } of photos) {
          await petService.addImage(editing.id, file);
        }
      } else {
        // New pet: multipart so the backend can save the uploaded images.
        const fd = new FormData();
        fd.append('name', form.name);
        fd.append('species', form.species);
        fd.append('breed', form.breed);
        fd.append('age_years', String(ageYears));
        fd.append('age_months', String(ageMonths));
        fd.append('gender', form.gender);
        if (weight) fd.append('weight_kg', weight);
        fd.append('color', form.color);
        fd.append('description', form.description);
        if (form.arrival_date) fd.append('arrival_date', form.arrival_date);
        fd.append('is_vaccinated', String(form.is_vaccinated));
        fd.append('is_neutered', String(form.is_neutered));
        // Every selected image is appended under the same field name so the
        // backend receives ALL of them for this one pet.
        photos.forEach(({ file }) => fd.append('images', file));
        await petService.create(fd);
      }
      toast.success(editing ? 'Pet updated' : 'Pet added', `${formatPetLabel(form.name)} has been saved to your pet records.`);
      clearPhotos();
      setRemovedPhotos([]);
      setShowForm(false);
      if (!editing) setScope('active');
      else setPage(1);
      setRefresh(current => current + 1);
    } catch (err) {
      setSubmitError(describeSaveError(err));
    } finally {
      setSaving(false);
    }
  };

  const previewImage = existingPhotos.find(photo => photo.is_primary)?.image || existingPhotos[0]?.image || photos[0]?.url;

  return (
    <div>
      <PageHeader title="Pets" subtitle="Manage pet inventory and details" />
      <div className="mb-6 flex items-center justify-between gap-4">
        <Button onClick={openNew}>Add New Pet</Button>
      </div>
      <RecordScopeTabs scope={scope} onChange={setScope} />
      <p className="mb-4 text-sm text-stone-600">Active shows pets in the center's current care. Adopted and inactive pets remain in History.</p>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select label="Status" value={statusFilter} onChange={event => setStatusFilter(event.target.value)} options={[
          { value: '', label: 'All statuses' },
          ...PET_STATUSES.filter(status => scope === 'all' || ACTIVE_PET_STATUSES.includes(status) === (scope === 'active'))
            .map(status => ({ value: status, label: formatDisplayName(status.replace(/_/g, ' ')) })),
        ]} />
        {!loading && !error && <p className="text-sm text-stone-500">{pagination.count} pet{pagination.count === 1 ? '' : 's'} in this view</p>}
      </div>

      {showForm && (
        <Card className="mb-6 overflow-hidden p-5 sm:p-7">
          <div className="mb-6 border-b border-stone-200 pb-5"><p className="section-label mb-2">Pet profile</p><h3 className="text-xl font-bold text-stone-900">{editing ? 'Edit Pet' : 'New Pet'}</h3><p className="mt-2 text-sm text-stone-500">Keep details clear and accurate. The preview shows how adopters will see this profile.</p></div>
          {submitError && <p role="alert" className="text-red-600 text-sm mb-4">{submitError}</p>}
          <div className="pet-editor-layout"><form onSubmit={handleSubmit} className="grid min-w-0 grid-cols-1 gap-x-5 gap-y-5 sm:grid-cols-2">
            <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            {editing && CARE_STATUSES.some(option => option.value === editing.status) && (
              <div>
                <Select label="Care status" value={form.status} onChange={event => setForm({ ...form, status: event.target.value })} options={CARE_STATUSES} />
                <p className="mt-2 text-xs text-stone-500">After assessment, choose Under Medical Care if treatment is needed. Choose Available only when the pet is cleared for adoption. Update medical findings in Health Records.</p>
              </div>
            )}
            <Select
              label="Species"
              value={form.species}
              onChange={(e) => setForm({ ...form, species: e.target.value })}
              options={[
                { value: 'dog', label: 'Dog' },
                { value: 'cat', label: 'Cat' },
                { value: 'other', label: 'Other' },
              ]}
            />
            <Input label="Breed" value={form.breed} onChange={(e) => setForm({ ...form, breed: e.target.value })} />
            <Input
              label="Age (Years)"
              type="number"
              min="0"
              max={MAX_AGE_YEARS}
              value={form.age_years}
              onChange={(e) => setForm({ ...form, age_years: e.target.value })}
              required
            />
            <Input
              label="Age (Months)"
              type="number"
              min="0"
              max={MAX_AGE_MONTHS}
              value={form.age_months}
              onChange={(e) => setForm({ ...form, age_months: e.target.value })}
              required
            />
            <Select
              label="Gender"
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value })}
              options={[
                { value: 'male', label: 'Male' },
                { value: 'female', label: 'Female' },
                { value: 'unknown', label: 'Unknown' },
              ]}
            />
            <Input
              label="Weight (kg)"
              type="number"
              min="0.01"
              max="9999.99"
              step="0.01"
              placeholder="e.g. 4.5"
              value={form.weight_kg}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
            />
            <Input label="Color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
            <Input
              label="Date arrived at the adoption center"
              type="date"
              max={philippineDate()}
              value={form.arrival_date}
              onChange={(e) => setForm({ ...form, arrival_date: e.target.value })}
            />
            <div className="sm:col-span-2 flex flex-wrap items-center gap-5 rounded-lg border border-stone-200 bg-stone-50 p-4">
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={form.is_vaccinated} onChange={(e) => setForm({ ...form, is_vaccinated: e.target.checked })} />
                Vaccinated
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={form.is_neutered} onChange={(e) => setForm({ ...form, is_neutered: e.target.checked })} />
                Neutered
              </label>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="pet-description" className="field-label mb-1.5">Description</label>
              <textarea
                id="pet-description"
                aria-describedby="pet-description-help"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={5}
                className="field-input pet-copy"
              /><p id="pet-description-help" className="mt-2 text-xs text-stone-500">Write in sentences. Paragraph breaks will appear in the adopter profile.</p>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="pet-photos" className="field-label mb-1">Pet Photos</label>

              {editing && (
                <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-medium text-slate-700">
                    Existing photos
                    {loadingPhotos ? ' (loading…)' : ` (${existingPhotos.length})`}
                  </p>
                  {!loadingPhotos && existingPhotos.length === 0 && (
                    <p className="text-sm text-slate-500 mt-1">This pet has no saved photos.</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {existingPhotos.map((photo, idx) => (
                      <div key={photo.id} className="relative">
                        <img
                          src={photo.image}
                          alt={`Saved photo ${idx + 1} of ${form.name || 'this pet'}`}
                          className="h-20 w-20 object-cover rounded-md border border-slate-200"
                        />
                        {photo.is_primary && (
                          <span className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-[10px] text-center rounded-b-md py-0.5">
                            Primary
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => markPhotoForRemoval(photo)}
                          aria-label={`Remove saved photo ${idx + 1}`}
                          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-black/80 text-white text-xs leading-none hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>

                  {removedPhotos.length > 0 && (
                    <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-2">
                      <p className="text-sm text-red-700">
                        {removedPhotos.length} photo{removedPhotos.length > 1 ? 's' : ''} will be deleted when you save:
                      </p>
                      <ul className="mt-1 flex flex-wrap gap-2">
                        {removedPhotos.map((photo) => (
                          <li
                            key={photo.id}
                            className="flex items-center gap-2 rounded border border-red-200 bg-white px-2 py-1 text-sm"
                          >
                            <img src={photo.image} alt="" className="h-8 w-8 object-cover rounded" />
                            <button
                              type="button"
                              onClick={() => undoPhotoRemoval(photo)}
                              className="text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-500"
                            >
                              Undo
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <input
                id="pet-photos"
                type="file"
                accept="image/*"
                multiple
                onChange={handlePhotoChange}
                className="w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-primary-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              {photoError && <p className="text-red-600 text-sm mt-1">{photoError}</p>}
              <div id="pet-photos-preview">
                {photos.length > 0 && (
                  <>
                    <p className="text-sm text-slate-600 mt-1">
                      New photos to upload ({photos.length}): {photos.map((p) => p.file.name).join(', ')}{' '}
                      <span className="text-slate-400">— selecting more images adds to this list instead of replacing it. Saved photos stay attached unless you remove them above.</span>
                    </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {photos.map((p, idx) => (
                      <div key={p.url} className="relative">
                        <img
                          src={p.url}
                          alt={`Selected pet photo ${idx + 1}: ${p.file.name}`}
                          className="h-20 w-20 object-cover rounded-md border border-slate-200"
                        />
                        {idx === 0 && existingPhotos.length === 0 && (
                          <span className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-[10px] text-center rounded-b-md py-0.5">
                            Primary
                          </span>
                        )}
                        {existingPhotos.length > 0 && (
                          <span className="absolute bottom-0 inset-x-0 bg-primary-600/80 text-white text-[10px] text-center rounded-b-md py-0.5">
                            New
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => removePhoto(idx)}
                          aria-label={`Remove selected photo ${p.file.name}`}
                          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-black/80 text-white text-xs leading-none hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
              </div>
            </div>
            <div className="sm:col-span-2 flex flex-wrap gap-3 border-t border-stone-200 pt-5">
              <Button type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save Changes' : 'Create Pet'}</Button>
              <Button variant="outline" onClick={() => setShowForm(false)} disabled={saving}>Cancel</Button>
            </div>
          </form>
          <aside aria-label="Adopter pet preview" className="min-w-0 rounded-xl border border-stone-200 bg-stone-50 p-4 xl:sticky xl:top-24">
            <p className="section-label mb-3">Adopter preview</p>
            <div className="pet-card">
              <div className="aspect-[4/3] bg-stone-100">
                {previewImage ? <img src={previewImage} alt="Pet profile preview" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-stone-400"><PawMark className="h-12 w-12" /></div>}
              </div>
              <div className="p-4">
                <h4 className="pet-name text-xl font-bold text-stone-900">{formatPetLabel(form.name) || 'Pet name'}</h4>
                <p className="mt-1 text-sm text-stone-600">{formatPetLabel(form.breed) || formatPetLabel(form.species)}{form.age_years !== '' && ` \u00b7 ${formatPetAge(Number(form.age_years), Number(form.age_months))}`}</p>
                <p className="mt-1 text-sm text-stone-500">{formatPetLabel(form.gender)}{form.weight_kg !== '' && ` · ${form.weight_kg} kg`}</p>
                {form.color.trim() && <p className="mt-3 border-t border-stone-200 pt-3 text-sm text-stone-600">{formatPetLabel(form.color)}</p>}
                <p className="pet-copy mt-3 text-stone-600">{form.description || 'Your description will appear here.'}</p>
              </div>
            </div>
            <p className="mt-3 text-xs leading-5 text-stone-500">Names, breeds, and colors use the same display format across both portals. Description wording stays as you write it.</p>
          </aside></div>
        </Card>
      )}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : pets.length === 0 ? (
        <Card><Empty message="No pets found." /></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {['Name', 'Species', 'Breed', 'Age', 'Weight (kg)', 'Status', ''].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-semibold text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {pets.map((pet) => (
                  <tr key={pet.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm font-medium text-slate-900">{formatPetLabel(pet.name)}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 capitalize">{pet.species}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{formatPetLabel(pet.breed)}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{formatPetAge(pet.age_years, pet.age_months)}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.weight_kg ?? 'Not recorded'}</td>
                    <td className="px-4 py-3 text-sm text-slate-600"><StatusBadge status={pet.status} /></td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(pet)} className="text-primary-600 hover:underline text-sm font-medium">Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {!error && pagination.count > 0 && <nav aria-label="Pet record pages" className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={loading || !pagination.previous} onClick={() => setPage(page - 1)}>Previous</Button>
        <span className="text-sm text-stone-600">Page {page} · {pagination.count} pets</span>
        <Button variant="outline" disabled={loading || !pagination.next} onClick={() => setPage(page + 1)}>Next</Button>
      </nav>}
    </div>
  );
}


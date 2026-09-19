import { useEffect, useRef, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Button, Input, Select } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { petService } from '../services/apiService';
import { formatPetAge } from '../utils/format';
import type { Pet, PetImage } from '../types';

const emptyForm = {
  name: '',
  species: 'dog',
  breed: '',
  age_years: '',
  gender: 'unknown',
  size: 'medium',
  color: '',
  description: '',
  arrival_date: '',
  is_vaccinated: false,
  is_neutered: false,
};

const MAX_AGE_YEARS = 40;

/** Maps a pet record to the editable form fields. */
function petToForm(pet: Pet) {
  return {
    name: pet.name,
    species: pet.species,
    breed: pet.breed,
    age_years: String(pet.age_years),
    gender: pet.gender,
    size: pet.size,
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
  const [pets, setPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Pet | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [adoptionFee, setAdoptionFee] = useState('');
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

  const load = () => {
    setLoading(true);
    setError('');
    petService
      .list()
      .then((res) => setPets(res.data.results))
      .catch(() => setError('Failed to load pets.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setAdoptionFee('');
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
    setAdoptionFee(String(pet.adoption_fee));
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
        setForm(petToForm(detail));
        setAdoptionFee(String(detail.adoption_fee));
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
    if (!Number.isInteger(ageYears) || ageYears < 0 || ageYears > MAX_AGE_YEARS) {
      setSubmitError(`Age must be a whole number of years between 0 and ${MAX_AGE_YEARS}.`);
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        // 1. Update the pet information. Photos live on their own endpoint, so
        //    this request can never remove a photo.
        await petService.update(editing.id, {
          ...form,
          age_years: ageYears,
          arrival_date: form.arrival_date || null,
          adoption_fee: Number(adoptionFee || 0),
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
        fd.append('gender', form.gender);
        fd.append('size', form.size);
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
      clearPhotos();
      setRemovedPhotos([]);
      setShowForm(false);
      load();
    } catch (err) {
      setSubmitError(describeSaveError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title="Pets" subtitle="Manage pet inventory and details" />
      <div className="mb-4">
        <Button onClick={openNew}>Add New Pet</Button>
      </div>

      {showForm && (
        <Card className="p-6 mb-6">
          <h3 className="font-semibold text-primary-900 mb-4">{editing ? 'Edit Pet' : 'New Pet'}</h3>
          {submitError && <p className="text-red-600 text-sm mb-4">{submitError}</p>}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <Select
              label="Species"
              value={form.species}
              onChange={(e) => setForm({ ...form, species: e.target.value })}
              options={[
                { value: 'dog', label: 'Dog' },
                { value: 'cat', label: 'Cat' },
                { value: 'bird', label: 'Bird' },
                { value: 'rabbit', label: 'Rabbit' },
                { value: 'other', label: 'Other' },
              ]}
            />
            <Input label="Breed" value={form.breed} onChange={(e) => setForm({ ...form, breed: e.target.value })} />
            <Input label="Age (years)" type="number" value={form.age_years} onChange={(e) => setForm({ ...form, age_years: e.target.value })} required />
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
            <Select
              label="Size"
              value={form.size}
              onChange={(e) => setForm({ ...form, size: e.target.value })}
              options={[
                { value: 'small', label: 'Small' },
                { value: 'medium', label: 'Medium' },
                { value: 'large', label: 'Large' },
                { value: 'extra_large', label: 'Extra Large' },
              ]}
            />
            <Input label="Color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
            <Input
              label="Date arrived at the adoption center"
              type="date"
              value={form.arrival_date}
              onChange={(e) => setForm({ ...form, arrival_date: e.target.value })}
            />
            <div className="md:col-span-2 flex items-center gap-4">
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={form.is_vaccinated} onChange={(e) => setForm({ ...form, is_vaccinated: e.target.checked })} />
                Vaccinated
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={form.is_neutered} onChange={(e) => setForm({ ...form, is_neutered: e.target.checked })} />
                Neutered
              </label>
            </div>
            <div className="md:col-span-2">
              <label className="field-label mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                className="field-input"
              />
            </div>
            <div className="md:col-span-2">
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
                          <span className="absolute bottom-0 inset-x-0 bg-slate-900/70 text-white text-[10px] text-center rounded-b-md py-0.5">
                            Primary
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => markPhotoForRemoval(photo)}
                          aria-label={`Remove saved photo ${idx + 1}`}
                          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-slate-900/80 text-white text-xs leading-none hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
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
                          <span className="absolute bottom-0 inset-x-0 bg-slate-900/70 text-white text-[10px] text-center rounded-b-md py-0.5">
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
                          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-slate-900/80 text-white text-xs leading-none hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
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
            <div className="md:col-span-2 flex gap-3">
              <Button type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save Changes' : 'Create Pet'}</Button>
              <Button variant="outline" onClick={() => setShowForm(false)} disabled={saving}>Cancel</Button>
            </div>
          </form>
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
                  {['Name', 'Species', 'Breed', 'Age', 'Status', 'Fee', ''].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-semibold text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {pets.map((pet) => (
                  <tr key={pet.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm font-medium text-slate-900">{pet.name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 capitalize">{pet.species}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.breed}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{formatPetAge(pet.age_years)}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.status.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">₱{pet.adoption_fee}</td>
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
    </div>
  );
}


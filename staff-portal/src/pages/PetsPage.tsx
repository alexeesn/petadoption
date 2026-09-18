import { useEffect, useRef, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Button, Input, Select } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { petService } from '../services/apiService';
import type { Pet } from '../types';

const emptyForm = {
  name: '',
  species: 'dog',
  breed: '',
  age_months: '',
  gender: 'unknown',
  size: 'medium',
  color: '',
  description: '',
  is_vaccinated: false,
  is_neutered: false,
};

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
  const [photoError, setPhotoError] = useState('');
  const [submitError, setSubmitError] = useState('');
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
    setPhotoError('');
    setShowForm(true);
  };

  const openEdit = (pet: Pet) => {
    setEditing(pet);
    setForm({
      name: pet.name,
      species: pet.species,
      breed: pet.breed,
      age_months: String(pet.age_months),
      gender: pet.gender,
      size: pet.size,
      color: pet.color,
      description: pet.description,
      is_vaccinated: pet.is_vaccinated,
      is_neutered: pet.is_neutered,
    });
    // Edit keeps sending the existing fee so PUT behavior is unchanged.
    setAdoptionFee(String(pet.adoption_fee));
    clearPhotos();
    setPhotoError('');
    setShowForm(true);
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setLoading(true);
    let request: Promise<unknown>;
    if (editing) {
      const payload = {
        ...form,
        age_months: Number(form.age_months),
        adoption_fee: Number(adoptionFee || 0),
      };
      request = petService.update(editing.id, payload);
    } else {
      // New pet: multipart so the backend can save the uploaded images.
      const fd = new FormData();
      fd.append('name', form.name);
      fd.append('species', form.species);
      fd.append('breed', form.breed);
      fd.append('age_months', String(Number(form.age_months)));
      fd.append('gender', form.gender);
      fd.append('size', form.size);
      fd.append('color', form.color);
      fd.append('description', form.description);
      fd.append('is_vaccinated', String(form.is_vaccinated));
      fd.append('is_neutered', String(form.is_neutered));
      // Every selected image is appended under the same field name so the
      // backend receives ALL of them for this one pet.
      photos.forEach(({ file }) => fd.append('images', file));
      request = petService.create(fd);
    }
    request
      .then(() => {
        clearPhotos();
        setShowForm(false);
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        const firstError = data
          ? Object.values(data).flat().map(String).join(' ')
          : 'Failed to save pet.';
        setSubmitError(firstError);
      })
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <PageHeader title="Pets" subtitle="Manage pet inventory and details" />
      <div className="mb-4">
        <Button onClick={openNew}>Add New Pet</Button>
      </div>

      {showForm && (
        <Card className="p-6 mb-6">
          <h3 className="font-semibold text-slate-900 mb-4">{editing ? 'Edit Pet' : 'New Pet'}</h3>
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
            <Input label="Age (months)" type="number" value={form.age_months} onChange={(e) => setForm({ ...form, age_months: e.target.value })} required />
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
              <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="md:col-span-2">
              <label htmlFor="pet-photos" className="block text-sm font-medium text-slate-700 mb-1">Pet Photos</label>
              <input
                id="pet-photos"
                type="file"
                accept="image/*"
                multiple
                onChange={handlePhotoChange}
                className="w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              {photoError && <p className="text-red-600 text-sm mt-1">{photoError}</p>}
              <div id="pet-photos-preview">
                {photos.length > 0 && (
                  <>
                    <p className="text-sm text-slate-600 mt-1">
                      Selected {photos.length} photo{photos.length > 1 ? 's' : ''}: {photos.map((p) => p.file.name).join(', ')}{' '}
                      <span className="text-slate-400">— selecting more images adds to this list; the first photo becomes the primary image.</span>
                    </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {photos.map((p, idx) => (
                      <div key={p.url} className="relative">
                        <img
                          src={p.url}
                          alt={`Selected pet photo ${idx + 1}: ${p.file.name}`}
                          className="h-20 w-20 object-cover rounded-md border border-slate-200"
                        />
                        {idx === 0 && (
                          <span className="absolute bottom-0 inset-x-0 bg-slate-900/70 text-white text-[10px] text-center rounded-b-md py-0.5">
                            Primary
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
              <Button type="submit">{editing ? 'Save Changes' : 'Create Pet'}</Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
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
                    <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {pets.map((pet) => (
                  <tr key={pet.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm font-medium text-slate-900">{pet.name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 capitalize">{pet.species}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.breed}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.age_months} mo</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{pet.status.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">₱{pet.adoption_fee}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(pet)} className="text-indigo-600 hover:underline text-sm font-medium">Edit</button>
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


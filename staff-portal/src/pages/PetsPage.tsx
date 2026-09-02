import { useEffect, useState } from 'react';
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
  adoption_fee: '0',
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
      adoption_fee: pet.adoption_fee,
      is_vaccinated: pet.is_vaccinated,
      is_neutered: pet.is_neutered,
    });
    setShowForm(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const payload = {
      ...form,
      age_months: Number(form.age_months),
      adoption_fee: Number(form.adoption_fee),
    };
    const request = editing
      ? petService.update(editing.id, payload)
      : petService.create(payload);
    request
      .then(() => {
        setShowForm(false);

      {showForm && (
        <Card className="p-6 mb-6">
          <h3 className="font-semibold text-slate-900 mb-4">{editing ? 'Edit Pet' : 'New Pet'}</h3>
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
            <Input label="Adoption Fee (₱)" type="number" value={form.adoption_fee} onChange={(e) => setForm({ ...form, adoption_fee: e.target.value })} />
            <div className="flex items-center gap-4">
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
            <div className="md:col-span-2 flex gap-3">
              <Button type="submit">{editing ? 'Save Changes' : 'Create Pet'}</Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

        load();
      })
      .catch(() => setError('Failed to save pet.'))
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <PageHeader title="Pets" subtitle="Manage pet inventory and details" />
      <div className="mb-4">
        <Button onClick={openNew}>Add New Pet</Button>
      </div>

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


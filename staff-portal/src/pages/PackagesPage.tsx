import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table, Button, Input, Textarea } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { packageService } from '../services/apiService';
import type { AdoptionPackage } from '../types';

export default function PackagesPage() {
  const [packages, setPackages] = useState<AdoptionPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', price: '0', is_active: true });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    packageService
      .list()
      .then((res) => setPackages(res.data.results))
      .catch(() => setError('Failed to load packages.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    setSubmitting(true);
    packageService
      .create(form)
      .then(() => {
        setSuccess('Package created.');
        setShowForm(false);
        setForm({ name: '', description: '', price: '0', is_active: true });
        load();
      })
      .catch(() => setSubmitError('Failed to create package.'))
      .finally(() => setSubmitting(false));
  };

  const handleDelete = (id: string) => {
    if (!window.confirm('Delete this package?')) return;
    packageService.remove(id).then(load).catch(() => setError('Failed to delete package.'));
  };

  return (
    <div>
      <PageHeader title="Adoption Packages" subtitle="Configure optional adoption packages" />
      <div className="mb-4">
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Add Package'}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-slate-900 mb-4">New Package</h3>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
            <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <Textarea label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Input
              label="Price (₱)"
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              required
            />
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              <span className="text-sm text-slate-700">Active</span>
            </label>
            {submitError && <p className="text-red-600 text-sm">{submitError}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Package'}
            </Button>
          </form>
        </Card>
      )}

      {success && <p className="mb-4 text-green-600 text-sm">{success}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : packages.length === 0 ? (
        <Card><Empty message="No packages configured." /></Card>
      ) : (
        <Card>
          <Table headers={['Name', 'Description', 'Price', 'Status', 'Actions']}>
            {packages.map((pkg) => (
              <tr key={pkg.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{pkg.name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{pkg.description}</td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  ₱{parseFloat(pkg.price).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{pkg.is_active ? 'Active' : 'Inactive'}</td>
                <td className="px-4 py-3">
                  <button onClick={() => handleDelete(pkg.id)} className="text-red-600 hover:underline text-sm">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

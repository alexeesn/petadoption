import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, StatusBadge, Table, Button, Select, Input } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { paymentService, applicationService, packageService } from '../services/apiService';
import type { Payment, Application, AdoptionPackage } from '../types';

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [packages, setPackages] = useState<AdoptionPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    application: '',
    package: '',
    amount: '',
    method: 'manual',
    status: 'paid',
  });
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([paymentService.list(), applicationService.list(), packageService.list()])
      .then(([payRes, appRes, pkgRes]) => {
        setPayments(payRes.data.results);
        setApps(appRes.data.results);
        setPackages(pkgRes.data.results);
      })
      .catch(() => setError('Failed to load payments.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    setSubmitting(true);
    const payload = { ...form, amount: form.amount || '0' };
    paymentService
      .create(payload)
      .then(() => {
        setSuccess('Payment recorded.');
        setShowForm(false);
        setForm({ application: '', package: '', amount: '', method: 'manual', status: 'paid' });
        load();
      })
      .catch(() => setSubmitError('Failed to record payment.'))
      .finally(() => setSubmitting(false));
  };

  const handleStatusChange = (id: string, status: string) => {
    paymentService
      .update(id, { status })
      .then(() => {
        setSuccess('Payment status updated.');
        load();
      })
      .catch(() => setError('Failed to update payment status.'))
      .finally(() => {});
  };

  return (
    <div>
      <PageHeader title="Payments" subtitle="Manage optional payments for adoption packages" />
      <div className="mb-4">
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Record Payment'}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-6">
          <h3 className="text-lg font-medium text-slate-900 mb-4">New Payment</h3>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
            <Select
              label="Application"
              value={form.application}
              onChange={(e) => setForm({ ...form, application: e.target.value })}
              options={[{ value: '', label: 'Select application' }, ...apps.map((a) => ({ value: a.id, label: `${a.pet_name} - ${a.adopter_email}` }))]}
            />
            <Select
              label="Package (optional)"
              value={form.package}
              onChange={(e) => setForm({ ...form, package: e.target.value })}
              options={[{ value: '', label: 'No package' }, ...packages.map((p) => ({ value: p.id, label: p.name }))]}
            />
            <Input
              label="Amount (₱)"
              type="number"
              step="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />

            <Select
              label="Method"
              value={form.method}
              onChange={(e) => setForm({ ...form, method: e.target.value })}
              options={[
                { value: 'manual', label: 'Manual (Cash/Transfer)' },
                { value: 'online', label: 'Online' },
              ]}
            />
            <Select
              label="Status"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              options={[
                { value: 'unpaid', label: 'Unpaid' },
                { value: 'partial', label: 'Partial' },
                { value: 'paid', label: 'Paid' },
                { value: 'refunded', label: 'Refunded' },
              ]}
            />
            {submitError && <p className="text-red-600 text-sm">{submitError}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Record Payment'}
            </Button>
          </form>
        </Card>
      )}

      {success && <p className="mb-4 text-green-600 text-sm">{success}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : payments.length === 0 ? (
        <Card><Empty message="No payments recorded." /></Card>
      ) : (
        <Card>
          <Table headers={['Application', 'Amount', 'Method', 'Status', 'Receipt', 'Actions']}>
            {payments.map((pay) => (
              <tr key={pay.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm text-slate-600">{pay.application}</td>
                <td className="px-4 py-3 text-sm font-medium text-slate-900">
                  ₱{parseFloat(pay.amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600 capitalize">{pay.method}</td>
                <td className="px-4 py-3"><StatusBadge status={pay.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">{pay.receipt_number || '—'}</td>
                <td className="px-4 py-3">
                  <select
                    value={pay.status}
                    onChange={(e) => handleStatusChange(pay.id, e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                  >
                    <option value="unpaid">Unpaid</option>
                    <option value="partial">Partial</option>
                    <option value="paid">Paid</option>
                    <option value="refunded">Refunded</option>
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

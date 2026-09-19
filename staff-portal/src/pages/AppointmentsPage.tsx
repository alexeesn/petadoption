import { useEffect, useState } from 'react';
import { Card, Loading, Empty, StatusBadge, Button } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { appointmentService } from '../services/apiService';
import type { Appointment } from '../types';
import { formatDate } from '../utils/format';

const STATUS_FILTERS = [
  { value: 'pending_confirmation', label: 'Pending confirmation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
];

/**
 * Review queue for onsite visit dates requested by adopters.
 *
 * Confirming or rejecting a requested date is a decision about the *date*
 * only — the adoption application keeps its own (approved) status, so a
 * rejected date never rejects the application.
 */
export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending_confirmation');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busyId, setBusyId] = useState('');
  const [rejectingId, setRejectingId] = useState('');
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    appointmentService
      .list(statusFilter ? { status: statusFilter } : {})
      .then((res) => setAppointments(res.data.results))
      .catch(() => setError('Failed to load appointment requests.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter]);

  const handleApprove = (appointment: Appointment) => {
    setBusyId(appointment.id);
    setError('');
    setSuccess('');
    appointmentService
      .approve(appointment.id)
      .then(() => {
        setSuccess(
          `Visit date confirmed for ${appointment.adopter_email}. The adoption record is now scheduled.`,
        );
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        setError(data?.error || data?.detail || 'Failed to confirm the appointment date.');
      })
      .finally(() => setBusyId(''));
  };

  const handleReject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setReasonError('A reason is required when rejecting a date.');
      return;
    }
    setBusyId(rejectingId);
    setError('');
    setSuccess('');
    appointmentService
      .reject(rejectingId, reason.trim())
      .then(() => {
        setSuccess('Requested date rejected. The adopter can choose another date.');
        setRejectingId('');
        setReason('');
        setReasonError('');
        load();
      })
      .catch((e: any) => {
        const data = e.response?.data;
        setError(data?.error || data?.detail || 'Failed to reject the appointment date.');
      })
      .finally(() => setBusyId(''));
  };

  return (
    <div>
      <PageHeader
        title="Appointments"
        subtitle="Adopters with an approved application choose an onsite visit date. Confirm or reject the requested date here — this does not change the application's own status."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.value || 'all'}
            onClick={() => setStatusFilter(filter.value)}
            className={`px-3 py-1.5 rounded-md text-sm border ${
              statusFilter === filter.value
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {success && <p className="mb-4 text-sm text-green-600">{success}</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {loading ? (
        <Loading />
      ) : appointments.length === 0 ? (
        <Card>
          <Empty message="No appointment requests for this filter." />
        </Card>
      ) : (
        <div className="space-y-4">
          {appointments.map((appointment) => (
            <Card key={appointment.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {appointment.pet_name} — {appointment.adopter_email}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Requested visit date:{' '}
                    <span className="font-medium">{formatDate(appointment.requested_date)}</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Application {appointment.application} · Requested{' '}
                    {formatDate(appointment.created_at)}
                  </p>
                  {appointment.status === 'rejected' && appointment.rejection_reason && (
                    <p className="mt-2 text-sm text-red-700">
                      Rejection reason: {appointment.rejection_reason}
                    </p>
                  )}
                </div>
                <StatusBadge status={appointment.status} />
              </div>

              {appointment.status === 'pending_confirmation' && (
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Button
                    onClick={() => handleApprove(appointment)}
                    disabled={busyId === appointment.id}
                  >
                    Confirm Date
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setRejectingId(rejectingId === appointment.id ? '' : appointment.id);
                      setReason('');
                      setReasonError('');
                    }}
                    disabled={busyId === appointment.id}
                  >
                    {rejectingId === appointment.id ? 'Cancel' : 'Reject Date'}
                  </Button>
                </div>
              )}

              {rejectingId === appointment.id && (
                <form onSubmit={handleReject} className="mt-4 max-w-xl space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-slate-700">
                      Reason for rejecting the date <span className="text-red-600">(required)</span>
                    </span>
                    <textarea
                      value={reason}
                      onChange={(e) => {
                        setReason(e.target.value);
                        setReasonError('');
                      }}
                      rows={3}
                      placeholder="The adopter will see this reason and can choose another date."
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </label>
                  {reasonError && <p className="text-sm text-red-600">{reasonError}</p>}
                  <Button type="submit" variant="danger" disabled={busyId === appointment.id}>
                    {busyId === appointment.id ? 'Saving...' : 'Reject Requested Date'}
                  </Button>
                </form>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
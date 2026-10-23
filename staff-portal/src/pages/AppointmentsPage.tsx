import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DecisionDialog } from '../components/DecisionDialog';
import { RescheduleRequestsPanel } from '../features/applications/RescheduleRequestsPanel';
import { Card, Loading, Empty, StatusBadge, Button } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { appointmentService } from '../services/apiService';
import type { Appointment } from '../types';
import { formatDate } from '../utils/format';

const STATUS_FILTERS = [
  { value: 'pending_confirmation', label: 'Pending confirmation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'no_show', label: 'No-show' },
  { value: 'rescheduled', label: 'Rescheduled' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: '', label: 'All' },
];

/**
 * Appointments is exclusively for appointment review and approval/rejection.
 *
 * Confirming or rejecting a requested date is a decision about the visit date
 * only — the adoption application keeps its own approved status, so a rejected
 * date never rejects the application. Confirming an appointment schedules the
 * visit but does not imply payment has been received or that adoption is completed.
 * Payments are recorded under Payment Records.
 */
export default function AppointmentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rescheduleTab = searchParams.get('tab') === 'reschedules';
  const [noShow, setNoShow] = useState<Appointment | null>(null);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ count: 0, next: false, previous: false });
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
      .list({ page, ...(statusFilter ? { status: statusFilter } : {}) })
      .then((res) => {
        const items = res.data.results as Appointment[];
        setAppointments(items);
        setPagination({ count: res.data.count, next: Boolean(res.data.next), previous: Boolean(res.data.previous) });
      })
      .catch(() => setError('Failed to load appointment requests.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter, page]);

  const handleApprove = (appointment: Appointment) => {
    setBusyId(appointment.id);
    setError('');
    setSuccess('');
    appointmentService
      .approve(appointment.id)
      .then(() => {
        setSuccess(
          `Visit date confirmed for ${appointment.adopter_email}. The adoption record is now scheduled. Payment may be recorded under Payment Records when received onsite.`,
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
        subtitle="Adopters with an approved application choose an onsite visit date. Confirm or reject the requested date here. Confirming a date does not record payment or complete the adoption; onsite payments are handled in Payment Records."
      />

      <div className="mb-4 flex flex-wrap gap-3" aria-label="Appointment sections">
        <Button variant={rescheduleTab ? 'outline' : 'primary'} onClick={() => setSearchParams({})}>Appointments</Button>
        <Button variant={rescheduleTab ? 'primary' : 'outline'} onClick={() => setSearchParams({ tab: 'reschedules' })}>Reschedule Requests</Button>
      </div>
      {rescheduleTab ? <RescheduleRequestsPanel onScheduleChanged={load} /> : <>
      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.value || 'all'}
            onClick={() => { setStatusFilter(filter.value); setPage(1); }}
            className={`px-3 py-1.5 rounded-md text-sm border ${
              statusFilter === filter.value
                ? 'bg-primary-600 text-white border-primary-600'
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
                  {appointment.status === 'confirmed' && (
                    <p className="mt-2 text-xs text-slate-500">
                      Appointment is confirmed. To record an onsite payment for this visit, go to{' '}
                      <span className="font-medium text-slate-700">Payment Records</span>.
                    </p>
                  )}
                </div>
                <StatusBadge status={appointment.status} />
              </div>
              {appointment.status === 'no_show' && <p className="mt-2 text-sm text-amber-800">
                No-show: {appointment.no_show_reason || 'No arrival recorded.'} A missed visit does not automatically cancel the adoption. See Reschedule Requests for follow-up decisions.
              </p>}
              {appointment.can_mark_no_show && <div className="mt-3">
                <Button variant="danger" onClick={() => setNoShow(appointment)}>Mark as No-show</Button>
              </div>}

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
                    <span className="field-label mb-1">
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
                      className="field-input"
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
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={loading || !pagination.previous} onClick={() => setPage((v) => v - 1)}>Previous</Button>
        <span className="text-sm">Page {page} · {pagination.count} appointments</span>
        <Button variant="outline" disabled={loading || !pagination.next} onClick={() => setPage((v) => v + 1)}>Next</Button>
      </div>
      </>}
      {noShow && <DecisionDialog title="Mark as No-show"
        description={`Record that the adopter did not attend ${noShow.pet_name}'s visit on ${formatDate(noShow.requested_date)}. This does not cancel the adoption.`}
        onClose={() => setNoShow(null)} onConfirm={async (reason) => {
          await appointmentService.markNoShow(noShow.id, reason);
          setSuccess('No-show recorded. The adopter has been notified and can request a new date.');
          load();
        }} />}
    </div>
  );
}

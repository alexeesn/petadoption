import { useEffect, useState } from 'react';
import { Button, Card, Empty, Loading, Select, StatusBadge } from '../../components/UI';
import { DecisionDialog } from '../../components/DecisionDialog';
import { rescheduleService } from '../../services/apiService';
import type { PaginatedResponse, RescheduleRequest } from '../../types';
import { formatDate, formatDateTime } from '../../utils/format';
import { useToast } from '../../context/ToastContext';

export function RescheduleRequestsPanel({ onScheduleChanged }: { onScheduleChanged: () => void }) {
  const toast = useToast();
  const [rows, setRows] = useState<RescheduleRequest[]>([]);
  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ count: 0, next: false, previous: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [decision, setDecision] = useState<{ row: RescheduleRequest; approve: boolean } | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    rescheduleService.list({ page, ...(status ? { status } : {}) })
      .then((response) => {
        if (!active) return;
        const data = response.data as PaginatedResponse<RescheduleRequest>;
        setRows(data.results);
        setPagination({ count: data.count, next: Boolean(data.next), previous: Boolean(data.previous) });
      })
      .catch(() => { if (active) setError('Could not load reschedule requests.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [status, page, refresh]);

  return (
    <section aria-label="Reschedule requests" className="space-y-4">
      {success && <p role="status" className="text-sm text-green-800">{success}</p>}
      <p className="text-sm text-slate-600">The current confirmed date stays valid until a new date is approved. No-show history is retained.</p>
      <Select label="Request status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
        options={[{ value: 'pending', label: 'Pending' }, { value: 'approved', label: 'Approved' },
          { value: 'rejected', label: 'Rejected' }, { value: 'cancelled', label: 'Cancelled' }, { value: '', label: 'All' }]} />
      {error && <p role="alert" className="text-sm text-red-700">{error} <button onClick={() => setRefresh((v) => v + 1)}>Retry</button></p>}
      {loading ? <Loading /> : rows.length === 0 ? <Empty message="No reschedule requests for this filter." /> : rows.map((row) => (
        <Card key={row.id} className="space-y-2 p-5">
          <h3 className="font-semibold text-slate-900">{row.pet_name} — {row.adopter_email}</h3>
          <p className="text-sm">Original date: {formatDate(row.original_date)} → Requested date: <strong>{formatDate(row.requested_date)}</strong></p>
          <p className="whitespace-pre-wrap text-sm text-slate-700">Reason: {row.reason}</p>
          <StatusBadge status={row.status} />
          <p className="text-xs text-slate-500">Requested {formatDateTime(row.created_at)}</p>
          {row.reviewed_at && <p className="text-xs text-slate-500">{row.decision_note} · {row.reviewed_by_email} · {formatDateTime(row.reviewed_at)}</p>}
          {row.status === 'pending' && <div className="flex flex-wrap gap-3 pt-2">
            <Button onClick={() => setDecision({ row, approve: true })}>Approve Reschedule</Button>
            <Button variant="danger" onClick={() => setDecision({ row, approve: false })}>Reject Request</Button>
          </div>}
        </Card>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={loading || !pagination.previous} onClick={() => setPage((v) => v - 1)}>Previous</Button>
        <span className="text-sm">Page {page} · {pagination.count} requests</span>
        <Button variant="outline" disabled={loading || !pagination.next} onClick={() => setPage((v) => v + 1)}>Next</Button>
      </div>
      {decision && <DecisionDialog title={decision.approve ? 'Approve Reschedule' : 'Reject Reschedule'}
        description={`${decision.row.pet_name}: ${formatDate(decision.row.original_date)} → ${formatDate(decision.row.requested_date)}. ${decision.approve ? 'Approve this new visit date without completing the adoption.' : 'Rejecting keeps the original appointment unchanged.'}`}
        requireReason={!decision.approve} onClose={() => setDecision(null)} onConfirm={async (reason) => {
          if (decision.approve) await rescheduleService.approve(decision.row.id);
          else await rescheduleService.reject(decision.row.id, reason);
          toast.success(decision.approve ? 'Reschedule approved' : 'Reschedule request rejected', `${decision.row.pet_name}'s request has been reviewed.`);
          setSuccess(decision.approve ? 'Reschedule approved. The adopter has been notified.' : 'Request rejected. The original appointment is unchanged and the adopter has been notified.');
          setRefresh((v) => v + 1);
          onScheduleChanged();
        }} />}
    </section>
  );
}

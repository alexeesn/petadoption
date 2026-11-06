import { useEffect, useState } from 'react';
import { Button, Card, StatusBadge } from '../../components/UI';
import { DecisionDialog } from '../../components/DecisionDialog';
import { paymentService } from '../../services/apiService';
import type { PaginatedResponse, Payment } from '../../types';
import { formatCurrency } from '../../utils/format';

export default function DeathPaymentReviews({ onResolved }: { onResolved: () => void }) {
  const [rows, setRows] = useState<Payment[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<Payment | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    paymentService.list({ death_review: 'required', page }).then(({ data }: { data: PaginatedResponse<Payment> }) => {
      if (!active) return;
      setRows(data.results); setCount(data.count); setNext(Boolean(data.next));
    }).catch(() => { if (active) setError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, refresh]);
  if (loading && !count) return <p role="status" className="mb-4 text-sm text-stone-500">Checking payment reviews…</p>;
  if (error) return <div role="alert" className="mb-5"><p className="text-sm text-red-700">Could not check payments requiring review after a pet death.</p><Button className="mt-2" variant="outline" onClick={() => setRefresh(value => value + 1)}>Retry payment reviews</Button></div>;
  if (!count) return null;
  return <section className="mb-6" aria-label="Payments requiring review after pet death"><Card className="space-y-4 border-amber-200 p-5"><h2 className="text-lg font-bold text-stone-900">Payments requiring review after pet death ({count})</h2><p className="text-sm text-stone-600">Contact the adopter and review any applicable refund. Recording an outcome clears this flag; it does not change the payment status, amount, or receipt.</p><div className="grid gap-3 lg:grid-cols-2">{rows.map(payment => <article key={payment.id} className="space-y-3 rounded-lg border border-stone-200 p-4"><h3 className="font-semibold text-stone-900">{payment.pet_name}</h3><p className="break-words text-sm text-stone-600">{payment.adopter_email}</p><p className="text-sm text-stone-800">{formatCurrency(payment.amount)} · <StatusBadge status={payment.status} /></p><p className="break-all text-xs text-stone-500">Receipt: {payment.receipt_number || 'Not issued'}</p><p className="text-sm text-stone-600">{payment.death_review_note}</p><Button variant="outline" onClick={() => setSelected(payment)}>Record review outcome</Button></article>)}</div>{(page > 1 || next) && <nav aria-label="Payment death review pages" className="flex items-center gap-3"><Button variant="outline" disabled={page === 1 || loading} onClick={() => setPage(value => value - 1)}>Previous reviews</Button><span className="text-sm text-stone-600">Page {page}</span><Button variant="outline" disabled={!next || loading} onClick={() => setPage(value => value + 1)}>Next reviews</Button></nav>}</Card>
    {selected && <DecisionDialog title="Save payment review outcome" description="Record the review and any arrangements made with the adopter. This does not issue a refund or change transaction history." reasonLabel="Review outcome (staff only)" onClose={() => setSelected(null)} onConfirm={async note => { await paymentService.resolveDeathReview(selected.id, note); setPage(1); setRefresh(value => value + 1); onResolved(); }} />}
  </section>;
}

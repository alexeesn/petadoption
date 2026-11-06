import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card, Empty, ErrorMessage, Loading, StatusBadge } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { surrenderService } from '../features/surrenders/service';
import type { SurrenderPage } from '../features/surrenders/types';
import { dateLabel, statusLabel, surrenderStatuses } from '../features/surrenders/types';

export default function SurrendersPage() {
  const [result, setResult] = useState<SurrenderPage | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('submitted');
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setResult(null); setFailed(false);
    surrenderService.list(page, status).then(data => { if (active) setResult(data); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [page, status, retry]);
  return <>
    <PageHeader title="Surrender Requests" subtitle="Assess owner requests, coordinate intake, and confirm physical handover." />
    <div className="mb-6 max-w-xs"><label htmlFor="surrender-status-filter" className="field-label">Request status</label><select id="surrender-status-filter" value={status} className="field-input" onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option>{surrenderStatuses.map(value => <option key={value} value={value}>{statusLabel(value)}</option>)}</select></div>
    {failed ? <><ErrorMessage message="Could not load surrender requests." /><Button onClick={() => setRetry(value => value + 1)}>Try again</Button></> : !result ? <Loading /> : !result.results.length ? <Empty message="No surrender requests match this view." /> : <>
      <div className="grid gap-4 lg:grid-cols-2">{result.results.map(request => <Card key={request.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><Link to={`/surrenders/${request.id}`} className="text-lg font-bold text-primary-700 hover:underline">{request.pet_name}</Link><StatusBadge status={request.status} /></div><p className="mt-2 text-sm text-stone-600">{statusLabel(request.species)} · {request.owner_name || request.owner_email}</p><p className="mt-1 break-all text-xs text-stone-500">{request.owner_email}</p><p className="mt-3 text-xs text-stone-500">Submitted {new Date(request.created_at).toLocaleString()}</p>{request.intake_date && <p className="mt-2 text-sm font-semibold text-stone-700">Intake: {dateLabel(request.intake_date)}</p>}<Link to={`/surrenders/${request.id}`} className="btn btn-outline mt-4">Review request</Link></Card>)}</div>
      <nav aria-label="Surrender request pages" className="mt-6 flex items-center justify-between gap-3"><Button variant="outline" disabled={!result.previous} onClick={() => setPage(value => value - 1)}>Previous</Button><p className="text-sm text-stone-600">Page {page} · {result.count} requests</p><Button variant="outline" disabled={!result.next} onClick={() => setPage(value => value + 1)}>Next</Button></nav>
    </>}
  </>;
}

import { FormEvent, useEffect, useState } from 'react';
import { Button, Card, Empty, Loading, Select } from '../../components/UI';
import { formatCurrency } from '../../utils/format';
import { operationalReports, reportError } from './service';
import type { OperationalReport, ReportFilters, ReportResult } from './types';
import ReportRows from './ReportRows';

function defaults(report?: OperationalReport): ReportFilters {
  return { date_basis: report?.date_bases[0]?.value || '', status: report?.default_status || '', date_from: '', date_to: '', search: '', species: '', review_status: '' };
}

export default function OperationalReports() {
  const [catalog, setCatalog] = useState<OperationalReport[] | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const [selected, setSelected] = useState('surrenders');
  const [draft, setDraft] = useState<ReportFilters>(defaults());
  const [applied, setApplied] = useState<ReportFilters>(defaults());
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [exportError, setExportError] = useState('');
  const [success, setSuccess] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [catalogRetry, setCatalogRetry] = useState(0);
  const report = catalog?.find(item => item.key === selected);
  const filtersChanged = Object.entries(draft).some(([key, value]) => value !== applied[key as keyof ReportFilters]);
  useEffect(() => {
    let active = true;
    setCatalogError('');
    operationalReports.catalog().then(data => {
      if (!active) return;
      const initial = data.find(item => item.key === 'surrenders') || data[0];
      setCatalog(data); setSelected(initial.key); setDraft(defaults(initial)); setApplied(defaults(initial));
    }).catch(async err => { const message = await reportError(err); if (active) setCatalogError(message); });
    return () => { active = false; };
  }, [catalogRetry]);
  useEffect(() => {
    if (!report) return;
    let active = true;
    setResult(null); setError('');
    operationalReports.read(selected, applied, page).then(data => { if (active) setResult(data); }).catch(async err => { const message = await reportError(err); if (active) setError(message); });
    return () => { active = false; };
  }, [report, selected, applied, page, refresh]);

  function choose(key: string) {
    const next = catalog?.find(item => item.key === key);
    setSelected(key); setDraft(defaults(next)); setApplied(defaults(next)); setPage(1);
    setSuccess(''); setFormError(''); setExportError('');
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.date_from && draft.date_to && draft.date_from > draft.date_to) { setFormError('End date must be on or after start date.'); return; }
    setFormError(''); setSuccess(''); setExportError(''); setApplied({ ...draft }); setPage(1);
  }
  async function download(format: 'csv' | 'pdf') {
    setDownloading(true); setExportError(''); setSuccess('');
    try {
      const blob = await operationalReports.export(selected, applied, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `pawconnect-${selected}-report.${format}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setSuccess(`${format.toUpperCase()} download started for all ${result?.count ?? 0} matching records.`);
    } catch (err) { setExportError(await reportError(err)); }
    finally { setDownloading(false); }
  }
  return <section className="mt-8 space-y-5" aria-label="Operational reports">
    <div><h2 className="text-xl font-bold text-stone-900">Operational Reports</h2><p className="mt-2 text-sm text-stone-600">Review requests, intake, verification, visits, adoption outcomes, pet history and payment reviews. Dates use Philippine time.</p></div>
    {catalogError ? <div role="alert" className="panel p-5"><p className="text-sm text-red-700">{catalogError}</p><Button className="mt-3" onClick={() => setCatalogRetry(value => value + 1)}>Retry report options</Button></div> : !catalog || !report ? <Loading label="Loading report options…" /> : <>
      <Card className="p-5 sm:p-6"><form onSubmit={submit} aria-label="Operational report filters" aria-describedby={formError ? 'operational-filter-error' : undefined}><fieldset disabled={downloading} className="space-y-5"><legend className="sr-only">Report filters</legend>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Select label="Operational report" value={selected} onChange={event => choose(event.target.value)} options={catalog.map(item => ({ value: item.key, label: item.title }))} /><Select label="Filter dates by" value={draft.date_basis} onChange={event => setDraft({ ...draft, date_basis: event.target.value })} options={report.date_bases} /><Select label="Report status" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value })} options={[{ value: '', label: 'All statuses' }, ...report.statuses]} />
          <label className="block"><span className="field-label">From date</span><input type="date" value={draft.date_from} onChange={event => setDraft({ ...draft, date_from: event.target.value })} className="field-input" /></label><label className="block"><span className="field-label">To date</span><input type="date" value={draft.date_to} onChange={event => setDraft({ ...draft, date_to: event.target.value })} className="field-input" /></label>
          <label className="block"><span className="field-label">Search records</span><input type="search" maxLength={200} value={draft.search} onChange={event => setDraft({ ...draft, search: event.target.value })} placeholder="Pet, adopter, email or reference" className="field-input" /></label>
          {report.supports_species && <Select label="Pet species" value={draft.species} onChange={event => setDraft({ ...draft, species: event.target.value })} options={[{ value: '', label: 'All species' }, { value: 'dog', label: 'Dog' }, { value: 'cat', label: 'Cat' }, { value: 'other', label: 'Other' }]} />}
          {report.extra_filters.review_status && <Select label="Death-related payment review" value={draft.review_status} onChange={event => setDraft({ ...draft, review_status: event.target.value })} options={[{ value: '', label: 'All review states' }, ...report.extra_filters.review_status]} />}
        </div>
        <p className="text-sm text-stone-600">{report.description}</p>
        {filtersChanged && <p role="status" className="text-sm text-stone-700">Apply your filter changes to update the results and downloads.</p>}
        {formError && <p id="operational-filter-error" role="alert" className="text-sm text-red-700">{formError}</p>}
        <div className="flex flex-wrap gap-3"><Button type="submit">Apply filters</Button><Button variant="outline" onClick={() => { setDraft(defaults(report)); setApplied(defaults(report)); setPage(1); setFormError(''); setSuccess(''); setExportError(''); }}>Reset filters</Button></div>
      </fieldset></form></Card>
      {error ? <div role="alert" className="panel p-5"><p className="text-sm text-red-700">{error}</p><Button className="mt-3" onClick={() => setRefresh(value => value + 1)}>Retry report</Button></div> : !result ? <Loading label="Loading operational report…" /> : <>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{result.stats.map(stat => <div key={stat.key} className="panel p-4"><dt className="text-sm text-stone-500">{stat.label}</dt><dd className="mt-2 break-words text-2xl font-bold text-stone-900">{stat.kind === 'money' ? formatCurrency(String(stat.value)) : stat.value}</dd></div>)}</dl>
        <Card className="space-y-4 p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-4"><div><h3 className="text-lg font-bold text-stone-900">{result.report.title} results</h3><p className="mt-1 text-xs text-stone-500">Date basis: {result.date_basis}. Counts and downloads cover all matching records.</p></div><div className="flex flex-wrap gap-3"><Button variant="outline" disabled={downloading || filtersChanged} onClick={() => { void download('csv'); }}>Export CSV</Button><Button variant="outline" disabled={downloading || filtersChanged} onClick={() => { void download('pdf'); }}>Export PDF</Button></div></div>
          {success && <p role="status" className="text-sm text-green-800">{success}</p>}{exportError && <p role="alert" className="text-sm text-red-700">{exportError}</p>}{downloading && <p role="status" className="text-sm text-stone-500">Preparing all matching report records…</p>}
          {result.results.length ? <ReportRows result={result} /> : <Empty message="No records match these report filters." />}
          <nav aria-label="Operational report pages" className="flex flex-wrap items-center justify-between gap-3"><Button variant="outline" disabled={!result.previous || downloading || filtersChanged} onClick={() => setPage(value => value - 1)}>Previous</Button><p className="text-sm text-stone-600">Page {page} · {result.count} {result.count === 1 ? 'record' : 'records'}</p><Button variant="outline" disabled={!result.next || downloading || filtersChanged} onClick={() => setPage(value => value + 1)}>Next</Button></nav>
        </Card>
      </>}
    </>}
  </section>;
}

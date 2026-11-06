import { Link } from 'react-router-dom';
import { StatusBadge } from '../../components/UI';
import { formatCurrency } from '../../utils/format';
import type { OperationalReport, ReportColumn, ReportResult } from './types';

function Cell({ column, row, report }: { column: ReportColumn; row: Record<string, string | null>; report: OperationalReport }) {
  const value = row[column.key];
  if (!value) return <span className="text-stone-500">Not recorded</span>;
  if (column.key === 'pet_name' && row.pet_id) return <Link to={`/pets?pet=${row.pet_id}`} className="font-semibold text-primary-700 hover:underline">{value}</Link>;
  if (column.kind === 'money') return <>{formatCurrency(value)}</>;
  if (column.kind === 'status') {
    if (report.key === 'pet-deaths' && column.key === 'status') return <span className="rounded-md bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-700">{value === 'active' ? 'Uncorrected death entry' : 'Corrected entry'}</span>;
    return <StatusBadge status={value} />;
  }
  if (column.kind === 'date' || column.kind === 'datetime') {
    const date = new Date(value.length === 10 ? `${value}T00:00:00+08:00` : value);
    return <time dateTime={value}>{column.kind === 'date' ? date.toLocaleDateString(undefined, { timeZone: 'Asia/Manila', dateStyle: 'medium' }) : date.toLocaleString(undefined, { timeZone: 'Asia/Manila', dateStyle: 'medium', timeStyle: 'short' })}</time>;
  }
  return <>{value}</>;
}

export default function ReportRows({ result }: { result: ReportResult }) {
  const columns = result.report.columns;
  return <>
    <div className="hidden overflow-x-auto md:block"><table className="min-w-full text-left text-sm"><caption className="sr-only">{result.report.title} report results</caption><thead className="border-b border-stone-200 bg-stone-50"><tr>{columns.map(column => <th key={column.key} scope="col" className="px-4 py-3 font-semibold text-stone-600">{column.label}</th>)}</tr></thead><tbody className="divide-y divide-stone-100">{result.results.map(row => <tr key={row.id}>{columns.map(column => <td key={column.key} className="min-w-[8rem] max-w-sm whitespace-pre-wrap break-words px-4 py-3 align-top text-stone-700"><Cell column={column} row={row} report={result.report} /></td>)}</tr>)}</tbody></table></div>
    <div className="space-y-3 md:hidden">{result.results.map(row => <article key={row.id} className="rounded-lg border border-stone-200 p-4"><h3 className="mb-4 font-semibold text-stone-900"><Cell column={columns[0]} row={row} report={result.report} /></h3><dl className="space-y-3">{columns.slice(1).map(column => <div key={column.key}><dt className="text-xs font-semibold text-stone-500">{column.label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm text-stone-700"><Cell column={column} row={row} report={result.report} /></dd></div>)}</dl></article>)}</div>
  </>;
}

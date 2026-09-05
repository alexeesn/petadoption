import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table, Select, Button } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { auditService } from '../services/apiService';
import type { AuditLog } from '../types';

const MODEL_OPTIONS = [
  { value: '', label: 'All Models' },
  { value: 'Application', label: 'Application' },
  { value: 'Pet', label: 'Pet' },
  { value: 'AdoptionRecord', label: 'Adoption Record' },
  { value: 'Review', label: 'Review' },
  { value: 'Payment', label: 'Payment' },
];

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const loadLogs = () => {
    setLoading(true);
    setError('');
    const params: Record<string, unknown> = {};
    if (modelFilter) params.model_name = modelFilter;
    if (actionFilter) params.action = actionFilter;

    auditService
      .list(params)
      .then((res: { data: { results?: AuditLog[]; count?: number } | AuditLog[] }) => {
        const results = Array.isArray(res.data) ? res.data : (res.data.results || []);
        setLogs(results);
      })
      .catch((err: { response?: { status: number } }) => {
        if (err.response?.status === 403) {
          setError('Access restricted: Audit logs require administrator permissions.');
        } else {
          setError('Failed to load audit logs.');
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelFilter]);

  return (
    <div>
      <PageHeader
        title="Audit Logs"
        subtitle="System-wide security and operational activity audit trail"
      />

      <div className="mb-4 flex flex-wrap gap-4 items-end">
        <Select
          label="Filter by Model"
          value={modelFilter}
          onChange={(e) => setModelFilter(e.target.value)}
          options={MODEL_OPTIONS}
        />
        <label className="block">
          <span className="block text-sm font-medium text-slate-700 mb-1">Action</span>
          <input
            type="text"
            placeholder="e.g. status_change"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <Button variant="outline" onClick={loadLogs}>
          Filter
        </Button>
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : logs.length === 0 ? (
        <Card>
          <Empty message="No audit logs recorded for this criteria." />
        </Card>
      ) : (
        <Card>
          <Table headers={['Timestamp', 'User', 'Action', 'Model', 'Object ID', 'Previous', 'New']}>
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-slate-800 font-medium">
                  {log.user_email || 'System / Anonymous'}
                </td>
                <td className="px-4 py-3 text-xs font-mono bg-slate-50 text-slate-700">
                  {log.action}
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{log.model_name}</td>
                <td className="px-4 py-3 text-xs font-mono text-slate-500 max-w-[120px] truncate">
                  {log.object_id}
                </td>
                <td className="px-4 py-3 text-xs text-amber-700 max-w-[160px] truncate">
                  {log.previous_value || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-emerald-700 font-medium max-w-[160px] truncate">
                  {log.new_value || '—'}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

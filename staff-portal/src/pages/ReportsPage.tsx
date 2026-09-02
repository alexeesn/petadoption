import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Button, Select } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { reportService } from '../services/apiService';

const REPORT_TYPES = [
  { value: 'adoption', label: 'Adoption Report' },
  { value: 'pet-inventory', label: 'Pet Inventory Report' },
  { value: 'adopter', label: 'Adopter Report' },
  { value: 'application', label: 'Application Report' },
  { value: 'health', label: 'Health Record Report' },
  { value: 'payment', label: 'Payment Report' },
];

export default function ReportsPage() {
  const [reportType, setReportType] = useState('adoption');
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = (type: string, from: string, to: string) => {
    setLoading(true);
    setError('');
    const params: Record<string, unknown> = {};
    if (from) params.date_from = from;
    if (to) params.date_to = to;
    const fetchers: Record<string, (p?: Record<string, unknown>) => Promise<any>> = {
      adoption: reportService.adoption,
      'pet-inventory': reportService.petInventory,
      adopter: reportService.adopter,
      application: reportService.application,
      health: reportService.health,
      payment: reportService.payment,
    };
    const fetcher = fetchers[type] || reportService.adoption;
    fetcher(params)
      .then((res: any) => setData(res.data.results || res.data || []))
      .catch(() => setError('Failed to load report.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(reportType, dateFrom, dateTo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportType]);

  const handleCsvExport = () => {
    reportService
      .csv(reportType, { date_from: dateFrom, date_to: dateTo })
      .then((res) => {
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${reportType}-report.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      })
      .catch(() => setError('Failed to export CSV.'));
  };

  return (
    <div>
      <PageHeader title="Reports" subtitle="Generate operational reports and export data" />
      <div className="mb-4 flex flex-wrap gap-4 items-end">
        <Select
          label="Report Type"
          value={reportType}
          onChange={(e) => setReportType(e.target.value)}
          options={REPORT_TYPES}
        />
        <label className="block">
          <span className="block text-sm font-medium text-slate-700 mb-1">From</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-slate-700 mb-1">To</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <Button variant="outline" onClick={() => load(reportType, dateFrom, dateTo)}>Apply Filters</Button>
        <Button variant="secondary" onClick={handleCsvExport}>Export CSV</Button>
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : (
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-medium text-slate-900 mb-4">
              {REPORT_TYPES.find((r) => r.value === reportType)?.label}
            </h3>
            {data.length === 0 ? (
              <p className="text-slate-500 py-8 text-center">No data available for this report.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      {Object.keys(data[0]).map((key) => (
                        <th
                          key={key}
                          scope="col"
                          className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider"
                        >
                          {key.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-200">
                    {data.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        {Object.values(row).map((val, i) => (
                          <td key={i} className="px-4 py-3 text-sm text-slate-600">
                            {val === null || val === undefined ? '—' : String(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

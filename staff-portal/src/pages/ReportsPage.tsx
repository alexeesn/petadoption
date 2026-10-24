import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Button, Select } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { reportService } from '../services/apiService';
import { useToast } from '../context/ToastContext';

const REPORT_TYPES = [
  { value: 'payment', label: 'Payment Report' },
  { value: 'adoption', label: 'Adoption Report' },
];

const MONTHS = [
  { value: '1', label: 'January' },
  { value: '2', label: 'February' },
  { value: '3', label: 'March' },
  { value: '4', label: 'April' },
  { value: '5', label: 'May' },
  { value: '6', label: 'June' },
  { value: '7', label: 'July' },
  { value: '8', label: 'August' },
  { value: '9', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
];

const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1;

const YEARS = [
  { value: String(currentYear - 2), label: String(currentYear - 2) },
  { value: String(currentYear - 1), label: String(currentYear - 1) },
  { value: String(currentYear), label: String(currentYear) },
  { value: String(currentYear + 1), label: String(currentYear + 1) },
];

export default function ReportsPage() {
  const toast = useToast();
  const [reportType, setReportType] = useState('payment');
  const [selectedMonth, setSelectedMonth] = useState(String(currentMonth));
  const [selectedYear, setSelectedYear] = useState(String(currentYear));
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [inventory, setInventory] = useState<{ total: number; by_status: Record<string, number> } | null>(null);
  const [inventoryError, setInventoryError] = useState('');

  useEffect(() => {
    let active = true;
    reportService.petInventory()
      .then(({ data }) => { if (active) setInventory(data.stats); })
      .catch(() => { if (active) setInventoryError('Could not load pet inventory totals.'); });
    return () => { active = false; };
  }, []);

  const handleDownloadPdf = () => {
    setDownloading(true);
    setError('');
    setSuccess('');

    const yearNum = parseInt(selectedYear, 10);
    const monthNum = parseInt(selectedMonth, 10);
    const monthObj = MONTHS.find((m) => m.value === selectedMonth);
    const monthLabel = monthObj ? monthObj.label : selectedMonth;

    const requestPromise =
      reportType === 'payment'
        ? reportService.monthlyPaymentsPdf(yearNum, monthNum)
        : reportService.monthlyAdoptionsPdf(yearNum, monthNum);

    requestPromise
      .then((res) => {
        const blob = res.data as Blob;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        const padMonth = String(monthNum).padStart(2, '0');
        anchor.download = `pawconnect-${reportType}-report-${yearNum}-${padMonth}.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        setSuccess(`${reportType === 'payment' ? 'Payment' : 'Adoption'} Report for ${monthLabel} ${yearNum} generated and downloaded.`);
        toast.success('Report ready', 'Your PDF download has started.');
      })
      .catch(() => {
        setError('Failed to generate monthly report PDF. Please try again.');
      })
      .finally(() => setDownloading(false));
  };

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Generate and download monthly completed operational reports in PDF format."
      />

      <Card className="mb-6 max-w-2xl p-6">
        <h3 className="text-lg font-semibold text-slate-900">Pet Inventory · All-time</h3>
        <p className="mt-1 text-sm text-slate-600">All pets recorded, including adopted and inactive pets retained in History.</p>
        {inventoryError ? <ErrorMessage message={inventoryError} /> : !inventory ? <Loading label="Loading inventory totals..." /> : (
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div><dt className="text-sm text-slate-500">Total Pets Recorded</dt><dd className="text-2xl font-bold">{inventory.total}</dd></div>
            <div><dt className="text-sm text-slate-500">Available</dt><dd className="text-2xl font-bold">{inventory.by_status.available ?? 0}</dd></div>
            <div><dt className="text-sm text-slate-500">Adopted</dt><dd className="text-2xl font-bold">{inventory.by_status.adopted ?? 0}</dd></div>
          </dl>
        )}
      </Card>

      <Card className="max-w-2xl p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-2">Monthly Completed Report</h3>
        <p className="text-xs text-slate-500 mb-6">
          Generate an official server-rendered PDF report containing only completed records for the selected month and year.
        </p>

        {error && (
          <div className="mb-4">
            <ErrorMessage message={error} />
          </div>
        )}

        {success && (
          <div
            role="status"
            className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
          >
            {success}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Select
            label="Report Type"
            value={reportType}
            onChange={(e) => {
              setReportType(e.target.value);
              setSuccess('');
              setError('');
            }}
            options={REPORT_TYPES}
          />

          <Select
            label="Month"
            value={selectedMonth}
            onChange={(e) => {
              setSelectedMonth(e.target.value);
              setSuccess('');
              setError('');
            }}
            options={MONTHS}
          />

          <Select
            label="Year"
            value={selectedYear}
            onChange={(e) => {
              setSelectedYear(e.target.value);
              setSuccess('');
              setError('');
            }}
            options={YEARS}
          />
        </div>

        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 mb-6">
          <h4 className="text-sm font-semibold text-slate-800 mb-1">
            {reportType === 'payment' ? 'Payment Report Scope' : 'Adoption Report Scope'}
          </h4>
          {reportType === 'payment' ? (
            <p className="text-xs text-slate-600 leading-relaxed">
              Includes only <strong>completed</strong> payment transactions whose payment date falls within the selected month.
              Pending, failed, refunded, and cancelled records are excluded from completed revenue totals.
              Shows the reporting period, included transactions, count, and completed amount total.
            </p>
          ) : (
            <p className="text-xs text-slate-600 leading-relaxed">
              Includes only <strong>completed</strong> adoption records finalized within the selected month based on the actual
              completion timestamp. Shows the reporting period, transaction IDs, pets, adopters, completion dates, and handling staff.
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={handleDownloadPdf}
            disabled={downloading}
          >
            {downloading ? 'Generating PDF…' : 'Download PDF'}
          </Button>
          {downloading && <Loading label="Preparing monthly PDF report..." />}
        </div>
      </Card>
    </div>
  );
}

import api from '../../services/api';
import type { OperationalReport, ReportFilters, ReportResult } from './types';

function params(filters: ReportFilters) {
  // Send blank status explicitly: an omitted death-report status defaults to
  // uncorrected entries, while the user can deliberately choose all entries.
  return Object.fromEntries(Object.entries(filters).filter(([key, value]) => key === 'status' || Boolean(value)));
}

export const operationalReports = {
  catalog: async () => (await api.get<{ reports: OperationalReport[] }>('/reports/operations/')).data.reports,
  read: async (key: string, filters: ReportFilters, page: number) => (await api.get<ReportResult>(`/reports/operations/${key}/`, { params: { ...params(filters), page } })).data,
  export: async (key: string, filters: ReportFilters, format: 'csv' | 'pdf') => (await api.get<Blob>(`/reports/operations/${key}/`, { params: { ...params(filters), export: format }, responseType: 'blob' })).data,
};

export async function reportError(error: unknown): Promise<string> {
  let data = (error as { response?: { data?: unknown } })?.response?.data;
  if (data instanceof Blob) {
    try { data = JSON.parse(await data.text()) as unknown; } catch { return 'Could not generate the report. Please try again.'; }
  }
  if (data && typeof data === 'object') return Object.values(data).flatMap(value => Array.isArray(value) ? value.map(String) : typeof value === 'string' ? [value] : []).join(' · ') || 'Could not load this report.';
  return 'Could not load this report. Check your connection and try again.';
}

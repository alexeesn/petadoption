export interface ReportOption { value: string; label: string }
export interface ReportColumn { key: string; label: string; kind: 'text' | 'date' | 'datetime' | 'status' | 'money' }
export interface OperationalReport {
  key: string;
  title: string;
  description: string;
  columns: ReportColumn[];
  date_bases: ReportOption[];
  statuses: ReportOption[];
  default_status: string;
  supports_species: boolean;
  extra_filters: Record<string, ReportOption[]>;
}
export interface ReportResult {
  report: OperationalReport;
  date_basis: string;
  count: number;
  next: string | null;
  previous: string | null;
  stats: { key: string; label: string; value: string | number; kind: 'number' | 'money' }[];
  results: Record<string, string | null>[];
}
export interface ReportFilters {
  date_basis: string;
  date_from: string;
  date_to: string;
  status: string;
  search: string;
  species: string;
  review_status: string;
}

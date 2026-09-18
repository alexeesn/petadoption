export function formatDate(value?: string): string {
  if (!value) return '—';
  try {
    const d = new Date(value);
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return value;
  }
}

export function formatDateTime(value?: string): string {
  if (!value) return '—';
  try {
    const d = new Date(value);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export function formatCurrency(value: string | number | null): string {
  const num = Number(value ?? 0);
  return new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' }).format(num);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Pet age is stored as whole years. 0 means the pet is younger than a year,
 * which is displayed as "Under 1 year" rather than a misleading "0 years".
 */
export function formatPetAge(years?: number | null): string {
  if (years === undefined || years === null) return '—';
  if (years <= 0) return 'Under 1 year';
  return years === 1 ? '1 year' : `${years} years`;
}

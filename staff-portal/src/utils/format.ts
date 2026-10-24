export function philippineDate(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
}

/** Display names and address labels consistently, keeping intentional casing. */
export function formatDisplayName(value?: string | null): string {
  return (value || '').trim().split(/\s+/).map(part =>
    part === part.toLocaleLowerCase()
      ? part.replace(/(^|[^\p{L}])(\p{L})/gu, (_match, separator: string, letter: string) => separator + letter.toUpperCase())
      : part
  ).join(' ')
}

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
 * Format pet age in readable text from years and months.
 *
 * Examples:
 *   formatPetAge(0, 6) -> "6 months"
 *   formatPetAge(1, 0) -> "1 year"
 *   formatPetAge(2, 3) -> "2 years and 3 months"
 *   formatPetAge(0, 0) -> "0 months"
 */
export function formatPetAge(years?: number | null, months?: number | null): string {
  if ((years === undefined || years === null) && (months === undefined || months === null)) {
    return '—';
  }
  const y = Math.max(0, years ?? 0);
  const m = Math.max(0, months ?? 0);

  if (y > 0 && m > 0) {
    const yStr = y === 1 ? '1 year' : `${y} years`;
    const mStr = m === 1 ? '1 month' : `${m} months`;
    return `${yStr} and ${mStr}`;
  }
  if (y > 0) {
    return y === 1 ? '1 year' : `${y} years`;
  }
  return m === 1 ? '1 month' : `${m} months`;
}

/** Shared pet-label presentation. Descriptions and stored values stay unchanged. */
export function formatPetLabel(value?: string | null): string {
  return (value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase()
    .replace(/(^|[\s/\-])(\p{L})/gu, (_match, separator: string, letter: string) => separator + letter.toLocaleUpperCase())
}

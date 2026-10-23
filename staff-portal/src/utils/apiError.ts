export function apiError(error: unknown, fallback = 'Could not save this decision.'): string {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data) return fallback;
  return Object.values(data).flatMap((value) =>
    typeof value === 'string' ? [value] : Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [],
  ).join(' · ') || fallback;
}

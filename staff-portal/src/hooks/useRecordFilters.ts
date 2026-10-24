import { useSearchParams } from 'react-router-dom';

export type RecordScope = 'active' | 'history' | 'all';

export function useRecordFilters() {
  const [params, setParams] = useSearchParams();
  const rawScope = params.get('scope');
  const scope: RecordScope = rawScope === 'history' || rawScope === 'all' ? rawScope : 'active';
  const rawPage = Number(params.get('page') || 1);
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const statusFilter = params.get('status') || '';

  const setScope = (value: RecordScope) => {
    const next = new URLSearchParams(params);
    next.set('scope', value);
    next.delete('status');
    next.delete('page');
    setParams(next);
  };
  const setStatusFilter = (value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set('status', value);
    else next.delete('status');
    next.delete('page');
    setParams(next);
  };
  const setPage = (value: number) => {
    const next = new URLSearchParams(params);
    next.set('page', String(value));
    setParams(next);
  };
  return { scope, page, statusFilter, setScope, setPage, setStatusFilter };
}

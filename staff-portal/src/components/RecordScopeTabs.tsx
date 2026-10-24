import type { RecordScope } from '../hooks/useRecordFilters';

export function RecordScopeTabs({ scope, onChange }: { scope: RecordScope; onChange: (value: RecordScope) => void }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Record views">
      {([
        ['active', 'Active'], ['history', 'History'], ['all', 'All records'],
      ] as const).map(([value, label]) => (
        <button key={value} type="button" aria-pressed={scope === value}
          className={`btn ${scope === value ? 'btn-primary' : 'btn-outline'}`}
          onClick={() => onChange(value)}>{label}</button>
      ))}
    </div>
  );
}

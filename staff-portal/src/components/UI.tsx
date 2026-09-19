import { ReactNode } from 'react';
import { PawMark } from './Icons';

interface StatusBadgeProps {
  status: string;
}

// Soft-tinted pills with a hairline ring and a small dot. Class names are
// spelled out in full so Tailwind can see them at build time.
const PILL = {
  gray: { pill: 'bg-stone-100 text-stone-700 ring-stone-400/30', dot: 'bg-stone-400' },
  blue: { pill: 'bg-sky-50 text-sky-800 ring-sky-600/20', dot: 'bg-sky-500' },
  amber: { pill: 'bg-amber-50 text-amber-800 ring-amber-600/25', dot: 'bg-amber-500' },
  purple: { pill: 'bg-purple-50 text-purple-800 ring-purple-600/20', dot: 'bg-purple-500' },
  // The brand palette has no orange, so this one uses literal values.
  orange: { pill: 'bg-[#fff1e6] text-[#9a3f0b] ring-[#e8590c]/25', dot: 'bg-[#e8590c]' },
  green: { pill: 'bg-green-50 text-green-800 ring-green-600/20', dot: 'bg-green-500' },
  emerald: { pill: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20', dot: 'bg-emerald-500' },
  red: { pill: 'bg-red-50 text-red-800 ring-red-600/20', dot: 'bg-red-500' },
};

const statusStyles: Record<string, keyof typeof PILL> = {
  draft: 'gray',
  submitted: 'blue',
  under_review: 'amber',
  pending_documents: 'purple',
  additional_info_requested: 'orange',
  approved: 'green',
  rejected: 'red',
  cancelled: 'gray',
  adoption_completed: 'emerald',
  available: 'green',
  pending: 'amber',
  reserved: 'blue',
  adopted: 'emerald',
  under_medical_care: 'red',
  inactive: 'gray',
  unpaid: 'amber',
  paid: 'green',
  partial: 'blue',
  refunded: 'gray',
  scheduled: 'blue',
  completed: 'green',
  returned: 'purple',
  pending_confirmation: 'amber',
  confirmed: 'green',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const style = PILL[statusStyles[status] ?? 'gray'];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ring-1 ring-inset ${style.pill}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  className = '',
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'secondary' | 'danger' | 'outline';
  disabled?: boolean;
  className?: string;
}) {
  const variants = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
    outline: 'btn-outline',
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`btn ${variants[variant]} ${className}`}>
      {children}
    </button>
  );
}

export function Input({
  label,
  type = 'text',
  value,
  onChange,
  required,
  placeholder,
  step,
}: {
  label: string;
  type?: string;
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  placeholder?: string;
  step?: string | number;
}) {
  return (
    <label className="block">
      <span className="field-label mb-1.5">{label}</span>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        placeholder={placeholder}
        step={step}
        className="field-input"
      />
    </label>
  );
}

export function Textarea({
  label,
  value,
  onChange,
  rows = 4,
  required,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  rows?: number;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="field-label mb-1.5">{label}</span>
      <textarea
        value={value}
        onChange={onChange}
        rows={rows}
        required={required}
        placeholder={placeholder}
        className="field-input"
      />
    </label>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="field-label mb-1.5">{label}</span>
      <select value={value} onChange={onChange} className="field-input">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Loading({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-stone-500" role="status">
      <span
        className="h-5 w-5 animate-spin rounded-full border-[3px] border-stone-200 border-t-primary-600"
        aria-hidden="true"
      />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function Empty({ message = 'No records found.' }: { message?: string }) {
  return (
    <div className="px-6 py-14 text-center">
      <div
        className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-accent-100 text-primary-900"
        aria-hidden="true"
      >
        <PawMark className="h-5 w-5" />
      </div>
      <p className="text-stone-500">{message}</p>
    </div>
  );
}

export function ErrorMessage({ message = 'Something went wrong.' }: { message?: string }) {
  return (
    <div
      className="relative mx-auto my-8 max-w-xl overflow-hidden rounded-lg border border-red-200 bg-red-50 py-4 pl-6 pr-5"
      role="alert"
    >
      <span className="absolute inset-y-0 left-0 w-1.5 bg-red-600" aria-hidden="true" />
      <p className="font-semibold text-red-700">{message}</p>
    </div>
  );
}

export function Table({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl">
      <table className="min-w-full">
        <thead className="border-b border-stone-200 bg-stone-50">
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-semibold text-stone-500">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 bg-white">{children}</tbody>
      </table>
    </div>
  );
}

import { useEffect, useId, useRef, useState } from 'react';
import { Button } from './UI';
import { apiError } from '../utils/apiError';

interface Props {
  title: string;
  description: string;
  requireReason?: boolean;
  confirmationLabel?: string;
  onConfirm: (reason: string) => Promise<void>;
  onClose: () => void;
}

export function DecisionDialog({ title, description, requireReason = true,
  confirmationLabel = 'I confirm this decision and understand its effect.', onConfirm, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const errorId = useId();
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { ref.current?.showModal(); }, []);

  return (
    <dialog ref={ref} aria-labelledby={titleId} aria-describedby={error ? errorId : undefined}
      onCancel={(e) => { e.preventDefault(); if (!busy) onClose(); }}
      className="w-[calc(100%-2rem)] max-w-lg rounded-xl border-0 bg-white p-6 shadow-xl backdrop:bg-black/50">
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        if (!confirmed || (requireReason && !reason.trim()) || busy) return;
        setBusy(true);
        setError('');
        try { await onConfirm(reason.trim()); onClose(); }
        catch (err) { setError(apiError(err)); }
        finally { setBusy(false); }
      }}>
        <h2 id={titleId} className="text-xl font-bold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-600">{description}</p>
        {requireReason && <label className="block">
          <span className="field-label mb-1">Reason (required; visible to the adopter)</span>
          <textarea className="field-input" rows={3} required maxLength={2000} disabled={busy}
            value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>}
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" required disabled={busy} checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)} className="mt-1" />
          <span>{confirmationLabel}</span>
        </label>
        {error && <p id={errorId} role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex flex-wrap justify-end gap-3">
          <Button variant="outline" disabled={busy} onClick={onClose}>Go back</Button>
          <Button type="submit" disabled={busy || !confirmed || (requireReason && !reason.trim())}>
            {busy ? 'Saving…' : title}
          </Button>
        </div>
      </form>
    </dialog>
  );
}

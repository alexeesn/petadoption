import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

interface SuccessNotice {
  id: number;
  title: string;
  description?: string;
}

interface ToastActions {
  success: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastActions | null>(null);

function Toast({ notice, dismiss }: { notice: SuccessNotice; dismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const timeout = window.setTimeout(() => dismiss(notice.id), 7000);
    return () => window.clearTimeout(timeout);
  }, [notice.id, paused, dismiss]);

  return (
    <li className="toast-notice" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false); }}
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); dismiss(notice.id); } }}>
      <span className="toast-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6" /></svg>
      </span>
      <div className="toast-copy" role="status" aria-atomic="true">
        <p className="toast-title">{notice.title}</p>
        {notice.description && <p className="toast-description">{notice.description}</p>}
      </div>
      <button type="button" className="toast-dismiss" aria-label={`Dismiss: ${notice.title}`} onClick={() => dismiss(notice.id)}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
      </button>
    </li>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<SuccessNotice[]>([]);
  const sequence = useRef(0);
  const success = useCallback((title: string, description?: string) => {
    const notice = { id: ++sequence.current, title, description };
    setNotices([notice]);
  }, []);
  const dismiss = useCallback((id: number) => setNotices(current => current.filter(notice => notice.id !== id)), []);
  const actions = useMemo(() => ({ success }), [success]);

  return (
    <ToastContext.Provider value={actions}>
      {children}
      <section className="toast-region" aria-label="Action confirmations">
        <ol className="toast-stack">{notices.map(notice => <Toast key={notice.id} notice={notice} dismiss={dismiss} />)}</ol>
      </section>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
}

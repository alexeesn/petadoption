import { useEffect, useRef, useState } from 'react';

interface GoogleIdResponse {
  credential?: string;
}

interface GoogleAccountsId {
  initialize: (config: { client_id: string; callback: (response: GoogleIdResponse) => void }) => void;
  renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
}

declare global {
  interface Window {
    google?: {
      accounts: { id: GoogleAccountsId };
    };
  }
}

interface GoogleSignInButtonProps {
  onCredential: (credential: string) => Promise<void> | void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

const GIS_SCRIPT_URL = 'https://accounts.google.com/gsi/client';

function loadGoogleIdentity(): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SCRIPT_URL}"]`);

    const waitForGoogle = () => {
      const started = Date.now();
      const interval = window.setInterval(() => {
        if (window.google?.accounts?.id) {
          window.clearInterval(interval);
          resolve();
        } else if (Date.now() - started > 8000) {
          window.clearInterval(interval);
          reject(new Error('Timed out waiting for Google Identity Services.'));
        }
      }, 100);
    };

    if (existing) {
      if (window.google?.accounts?.id) {
        resolve();
      } else {
        waitForGoogle();
      }
      return;
    }

    const script = document.createElement('script');
    script.src = GIS_SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.onload = () => waitForGoogle();
    script.onerror = () => reject(new Error('Failed to load Google Identity Services.'));
    document.head.appendChild(script);
  });
}

export default function GoogleSignInButton({ onCredential, onError, disabled }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState('');
  const busyRef = useRef(false);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      setUnavailable('Google sign-in is not configured for this environment.');
      return;
    }
    if (disabled) return;
    if (containerRef.current?.childElementCount) return; // already rendered

    let cancelled = false;

    loadGoogleIdentity()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => {
            if (busyRef.current) return;
            if (response?.credential) {
              busyRef.current = true;
              Promise.resolve(onCredential(response.credential))
                .catch((err: unknown) => {
                  const message =
                    (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
                    'Google sign-in failed. Please try again.';
                  onError?.(message);
                })
                .finally(() => {
                  busyRef.current = false;
                });
            } else {
              onError?.('Google sign-in did not return a credential.');
            }
          },
        });
        if (containerRef.current && !containerRef.current.childElementCount) {
          window.google.accounts.id.renderButton(containerRef.current, {
            theme: 'outline',
            size: 'large',
            text: 'continue_with',
            shape: 'pill',
            width: 340,
          });
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setUnavailable(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [onCredential, onError, disabled]);

  if (unavailable) {
    return <p className="mt-2 text-center text-sm text-slate-400">{unavailable}</p>;
  }

  return (
    <div>
      <div ref={containerRef} className="flex justify-center" aria-label="Continue with Google" />
    </div>
  );
}
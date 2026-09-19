import { ReactNode } from 'react';
import { BrandTile, CollarTagArt } from '../components/Icons';

export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      {/* Brand panel (desktop only, decorative) */}
      <aside className="relative hidden overflow-hidden bg-primary-900 lg:flex lg:flex-col lg:justify-between lg:p-12" aria-hidden="true">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-400 text-primary-900">
            <svg viewBox="0 0 32 32" className="h-6 w-6" fill="currentColor">
              <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
              <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
              <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
              <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
              <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
            </svg>
          </span>
          <span className="font-display text-xl font-bold text-white">Pawnscape</span>
        </div>
        <CollarTagArt className="mx-auto h-auto w-full max-w-md" />
        <div className="h-6" />
      </aside>

      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center lg:text-left">
            <div className="mb-4 flex justify-center lg:hidden">
              <BrandTile className="h-12 w-12" />
            </div>
            <h1 className="text-3xl font-extrabold text-primary-900">Staff Portal</h1>
            <p className="mt-1 text-stone-600">Pet Adoption Management System</p>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

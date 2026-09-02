import { ReactNode } from 'react';

export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Staff Portal</h1>
          <p className="text-sm text-slate-600">Pet Adoption Management System</p>
        </div>
        {children}
      </div>
    </div>
  );
}

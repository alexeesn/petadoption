import { ReactNode } from 'react';
import { BrandTile, Icon } from '../components/Icons';
import ThemeToggle from '../components/ThemeToggle';

export function PublicLayout({ children }: { children: ReactNode }) {
  return <div className="portal-shell relative min-w-0 lg:grid lg:grid-cols-[1fr_1.1fr]">
    <aside className="staff-auth-aside hidden min-h-screen flex-col justify-between p-12 lg:flex" aria-label="PawConnect staff workspace">
      <div className="flex items-center gap-3"><BrandTile className="h-11 w-11"/><div><p className="text-xl font-bold text-stone-900">PawConnect</p><p className="mt-1 text-xs font-medium text-stone-500">The staff workspace</p></div></div>
      <div className="my-16 max-w-md"><p className="section-label mb-5">Good care takes a team</p><h2 className="text-5xl font-semibold leading-[1.12] tracking-tight text-stone-900">Every detail.<br/><span className="text-primary-700">Every little life.</span></h2><p className="mt-6 text-base leading-8 text-stone-600">One calm, organized place to coordinate applications, visits, and the pets in your care.</p><div className="mt-10 grid grid-cols-2 gap-3">{[['clipboard','Applications'],['calendar','Appointments'],['paw','Pet care'],['home','Adoption records']].map(([icon,label]) => <div key={label} className="flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-3 text-xs font-medium text-stone-700"><Icon name={icon} className="h-4 w-4 text-primary-700"/>{label}</div>)}</div></div>
      <p className="text-xs text-stone-500">For authorized PawConnect staff and administrators.</p>
    </aside>
    <div className="relative flex min-h-screen min-w-0 items-center justify-center px-4 py-20 sm:px-6"><div className="absolute right-5 top-5"><ThemeToggle/></div><div className="w-full min-w-0 max-w-md"><div className="mb-7"><div className="mb-6 flex items-center gap-3 lg:hidden"><BrandTile className="h-10 w-10"/><p className="text-xl font-bold text-stone-900">PawConnect</p></div><p className="section-label mb-3">PawConnect staff workspace</p><h1 className="text-3xl font-bold text-stone-900">Welcome back.</h1><p className="mt-3 text-sm text-stone-600">Sign in to continue caring for your community.</p></div>{children}</div></div>
  </div>;
}

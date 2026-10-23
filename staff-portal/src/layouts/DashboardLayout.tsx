import { ReactNode, useEffect, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import NotificationBell from '../components/NotificationBell';
import { useAuth } from '../context/AuthContext';
import { useSidebarCounts } from '../hooks/useSidebarCounts';
import type { SidebarBadgeKey } from '../hooks/useSidebarCounts';
import { BrandTile, Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  /** Sidebar module that shows an unread-notification badge, when applicable. */
  badge?: SidebarBadgeKey;
}

interface NavSection {
  title: string;
  items: NavItem[];
  /** Rendered only for administrators. */
  adminOnly?: boolean;
}

/**
 * Workflow-based navigation sections: staff operations are grouped by the
 * workflow they belong to instead of being listed as unrelated top-level links.
 *
 * Deliberately absent from the sidebar (their routes and backend functionality
 * are unchanged, they simply are not standalone destinations):
 *  - Documents: application documents are handled inside Application Detail.
 *  - Reviews: review decisions are handled inside Application Detail.
 *  - Packages: package selection is no longer part of the PawConnect workflow.
 *  - Notifications: reached from the notification bell in the header.
 */
const navSections: NavSection[] = [
  {
    title: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: 'dashboard' }],
  },
  {
    title: 'Adoption Management',
    items: [
      { to: '/applications', label: 'Applications', icon: 'clipboard', badge: 'applications' },
      { to: '/appointments', label: 'Appointments', icon: 'calendar', badge: 'appointments' },
      { to: '/adopters', label: 'Adopters', icon: 'user' },
    ],
  },
  {
    title: 'Pet Management',
    items: [
      { to: '/pets', label: 'Pets', icon: 'paw' },
      { to: '/health', label: 'Health Records', icon: 'pulse' },
    ],
  },
  {
    title: 'Adoption Records',
    items: [
      { to: '/adoptions', label: 'Adoption Records', icon: 'home' },
      { to: '/payments', label: 'Payment Records', icon: 'card' },
    ],
  },
  {
    title: 'Reports',
    items: [{ to: '/reports', label: 'Reports', icon: 'chart' }],
  },
  {
    title: 'Administration',
    adminOnly: true,
    items: [{ to: '/audit', label: 'Audit Logs', icon: 'lock' }],
  },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { counts, markModuleRead } = useSidebarCounts();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const drawer = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!sidebarOpen) return;
    drawer.current?.querySelector<HTMLAnchorElement>('a')?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setSidebarOpen(false); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [sidebarOpen]);
  const visibleSections = navSections.filter(section => !section.adminOnly || user?.role === 'admin');
  const current = visibleSections.flatMap(section => section.items).find(item => item.to === '/' ? pathname === '/' : pathname.startsWith(item.to));
  const handleLogout = async () => { await logout(); navigate('/login'); };
  return (
    <div className="portal-shell flex">
      {sidebarOpen && <button type="button" aria-label="Close navigation" className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />}
      <aside ref={drawer} id="staff-navigation" aria-label="Staff workspace" className={`fixed inset-y-0 left-0 z-50 w-64 shrink-0 flex-col staff-sidebar md:sticky md:top-0 md:flex md:h-screen ${sidebarOpen ? 'flex' : 'hidden'}`}>
        <div className="flex h-[4.5rem] shrink-0 items-center gap-3 border-b border-stone-200 px-6"><BrandTile className="h-10 w-10" /><div><p className="font-display text-lg font-bold tracking-tight text-stone-900">PawConnect</p><p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[.18em] text-stone-500">Staff workspace</p></div></div>
        <nav className="flex-1 space-y-5 overflow-y-auto px-4 py-5" aria-label="Staff portal sections">
          {visibleSections.map(section => <div key={section.title}><h2 className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[.08em] text-stone-500">{section.title}</h2><ul className="space-y-1">{section.items.map(item => {
            const badgeCount = item.badge ? counts[item.badge] : 0;
            return <li key={item.to}><NavLink to={item.to} end={item.to === '/'} onClick={() => { setSidebarOpen(false); if (item.badge && badgeCount > 0) void markModuleRead(item.badge); }} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors staff-nav-link ${isActive ? 'is-active' : ''}`}><Icon name={item.icon} className="h-[18px] w-[18px] shrink-0"/><span className="min-w-0 flex-1 truncate">{item.label}</span>{item.badge && badgeCount > 0 && <span className="rounded-md bg-[#b42336] px-1.5 py-0.5 text-[10px] font-semibold text-white">{badgeCount > 99 ? '99+' : badgeCount}<span className="sr-only"> unread notifications</span></span>}</NavLink></li>;
          })}</ul></div>)}
        </nav>
        <div className="shrink-0 border-t border-stone-200 p-4"><div className="mb-3 flex items-center gap-3 px-2"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-50 text-primary-700"><Icon name="user" className="h-5 w-5"/></span><div className="min-w-0"><p className="truncate text-sm font-semibold text-stone-900">{user?.full_name || 'PawConnect team'}</p><p className="truncate text-xs text-stone-500">{user?.role === 'admin' ? 'Administrator' : 'Staff member'}</p></div></div><button type="button" onClick={handleLogout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold text-stone-600 hover:bg-stone-100 hover:text-stone-900"><Icon name="logout" className="h-4 w-4"/>Logout</button></div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-[4.5rem] items-center justify-between gap-3 portal-header border-b px-4 sm:px-6 lg:px-9">
          <div className="flex min-w-0 items-center gap-3"><button type="button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" aria-controls="staff-navigation" aria-expanded={sidebarOpen} className="icon-button shrink-0 md:hidden"><svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button><div className="min-w-0"><p className="text-[9px] font-bold uppercase tracking-[.13em] text-stone-500 sm:text-[10px]"><span className="sm:hidden">PawConnect staff</span><span className="hidden sm:inline">Team workspace</span></p><p className="truncate text-sm font-semibold text-stone-800">{current?.label || 'Workspace'}</p></div></div>
          <div className="flex shrink-0 items-center gap-2"><span className="mr-2 hidden rounded-full border border-stone-200 px-3 py-1 text-[11px] font-semibold text-stone-600 lg:inline-flex">{user?.role === 'admin' ? 'Administrator' : 'Staff'}</span><ThemeToggle/><NotificationBell open={notificationsOpen} onOpenChange={setNotificationsOpen}/></div>
        </header>
        <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
        <footer className="px-6 py-5 text-xs text-stone-500">PawConnect · Staff workspace</footer>
      </div>
    </div>
  );
}
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return <div className="mb-7"><h2 className="text-2xl font-bold tracking-tight text-stone-900 sm:text-3xl">{title}</h2>{subtitle && <p className="mt-2 text-sm text-stone-500">{subtitle}</p>}</div>;
}

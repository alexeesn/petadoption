import { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { BrandTile, Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
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
      { to: '/applications', label: 'Applications', icon: 'clipboard' },
      { to: '/appointments', label: 'Appointments', icon: 'calendar' },
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
      { to: '/payments', label: 'Payments', icon: 'card' },
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

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const visibleSections = navSections.filter(
    (section) => !section.adminOnly || user?.role === 'admin',
  );

  const initial = (user?.full_name || user?.email || '?').trim().charAt(0).toUpperCase();

  return (
    <div className="flex min-h-screen bg-stone-100">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 flex-shrink-0 flex-col border-r border-stone-200 bg-white md:flex">
        <div className="flex items-center gap-3 border-b border-stone-200 px-5 py-5">
          <BrandTile />
          <div>
            <h1 className="font-display text-lg font-bold leading-5 text-primary-900">Pet Adoption</h1>
            <p className="text-xs text-stone-500">Staff Portal</p>
          </div>
        </div>
        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5" aria-label="Staff portal sections">
          {visibleSections.map((section) => (
            <div key={section.title}>
              <h2 className="px-3 pb-1.5 font-sans text-xs font-semibold text-stone-500">{section.title}</h2>
              <ul className="space-y-0.5">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/'}
                      className={({ isActive }) =>
                        `relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                          isActive
                            ? 'bg-primary-50 text-primary-900 before:absolute before:inset-y-1.5 before:-left-3 before:w-1 before:rounded-r-full before:bg-accent-400'
                            : 'text-stone-600 hover:bg-stone-100 hover:text-primary-900'
                        }`
                      }
                    >
                      <Icon name={item.icon} className="h-[18px] w-[18px] shrink-0" />
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-stone-200 p-4">
          <div className="flex items-center gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-100 font-display text-sm font-bold text-primary-800"
              aria-hidden="true"
            >
              {initial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-stone-900">{user?.full_name}</p>
              <p className="truncate text-xs text-stone-500">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="mt-3 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs font-semibold text-stone-600 transition-colors hover:bg-red-50 hover:text-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            <Icon name="logout" className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>

      {/* Content column: header with the notification bell + grouped nav on small screens */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-stone-200 bg-white/90 backdrop-blur">
          <div className="flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-2.5 md:hidden">
              <BrandTile className="h-8 w-8" />
              <h1 className="font-display text-lg font-bold text-primary-900">Staff Portal</h1>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <NavLink
                to="/notifications"
                aria-label="Notifications"
                className={({ isActive }) =>
                  `flex h-10 w-10 items-center justify-center rounded-full transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-800'
                      : 'text-stone-500 hover:bg-stone-100 hover:text-primary-900'
                  }`
                }
              >
                <Icon name="bell" className="h-5 w-5" />
              </NavLink>
              <button
                onClick={handleLogout}
                className="rounded-md px-2.5 py-1.5 text-xs font-semibold text-stone-600 hover:bg-stone-100 hover:text-primary-900 md:hidden"
              >
                Logout
              </button>
            </div>
          </div>
          {/* Section links for small screens (the sidebar is desktop-only) */}
          <nav className="flex gap-1 overflow-x-auto border-t border-stone-100 px-4 py-2 md:hidden" aria-label="Staff portal sections (mobile)">
            {visibleSections.flatMap((section) => section.items).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium ${
                    isActive ? 'bg-primary-900 text-white' : 'text-stone-600'
                  }`
                }
              >
                <Icon name={item.icon} className="h-4 w-4" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="flex-1 p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-7">
      <h2 className="text-3xl font-extrabold tracking-tight text-primary-900">{title}</h2>
      {subtitle && <p className="mt-1.5 text-stone-600">{subtitle}</p>}
    </div>
  );
}

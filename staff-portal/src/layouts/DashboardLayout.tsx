import { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface NavItem {
  to: string;
  label: string;
  icon: string;
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
    items: [{ to: '/', label: 'Dashboard', icon: '📊' }],
  },
  {
    title: 'Adoption Management',
    items: [
      { to: '/applications', label: 'Applications', icon: '📋' },
      { to: '/appointments', label: 'Appointments', icon: '📅' },
      { to: '/adopters', label: 'Adopters', icon: '👤' },
    ],
  },
  {
    title: 'Pet Management',
    items: [
      { to: '/pets', label: 'Pets', icon: '🐾' },
      { to: '/health', label: 'Health Records', icon: '🩺' },
    ],
  },
  {
    title: 'Adoption Records',
    items: [
      { to: '/adoptions', label: 'Adoption Records', icon: '🏠' },
      { to: '/payments', label: 'Payments', icon: '💳' },
    ],
  },
  {
    title: 'Reports',
    items: [{ to: '/reports', label: 'Reports', icon: '📈' }],
  },
  {
    title: 'Administration',
    adminOnly: true,
    items: [{ to: '/audit', label: 'Audit Logs', icon: '🔒' }],
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

  return (
    <div className="min-h-screen bg-slate-100 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex-shrink-0 hidden md:flex flex-col">
        <div className="px-5 py-4 border-b border-slate-700">
          <h1 className="text-lg font-bold">Pet Adoption</h1>
          <p className="text-xs text-slate-400">Staff Portal</p>
        </div>
        <nav className="flex-1 px-3 pb-4 overflow-y-auto" aria-label="Staff portal sections">
          {visibleSections.map((section) => (
            <div key={section.title} className="pt-4">
              <h2 className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {section.title}
              </h2>
              <ul className="space-y-1">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                          isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                        }`
                      }
                    >
                      <span aria-hidden="true">{item.icon}</span>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-slate-700">
          <p className="text-sm text-slate-300 truncate">{user?.full_name}</p>
          <p className="text-xs text-slate-500 mb-2">{user?.email}</p>
          <button
            onClick={handleLogout}
            className="text-xs text-red-400 hover:text-red-300 focus:outline-none"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Content column: header with the notification bell + grouped nav on small screens */}
      <div className="flex flex-col flex-1 min-w-0">
        <header className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between gap-3 md:bg-white md:text-slate-700 md:border-b md:border-slate-200 md:px-6 md:justify-end">
          <h1 className="text-lg font-bold md:hidden">Staff Portal</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-300 md:hidden">{user?.full_name}</span>
            {/* Single notification entry point: the Notifications page is reached from here */}
            <NavLink
              to="/notifications"
              aria-label="Notifications"
              title="Notifications"
              className={({ isActive }) =>
                `inline-flex items-center justify-center rounded-md px-2 py-1.5 text-lg leading-none focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  isActive
                    ? 'text-indigo-300 md:text-indigo-600'
                    : 'text-slate-200 md:text-slate-600 hover:bg-white/10 md:hover:bg-slate-100'
                }`
              }
            >
              <span aria-hidden="true">🔔</span>
            </NavLink>
            <button
              onClick={handleLogout}
              className="text-xs text-red-400 md:hidden focus:outline-none"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Mobile section nav (same workflow sections as the sidebar) */}
        <nav
          className="md:hidden bg-white border-b border-slate-200 px-3 py-2 flex gap-3 overflow-x-auto"
          aria-label="Staff portal sections"
        >
          {visibleSections.map((section) => (
            <div
              key={section.title}
              className="flex flex-col gap-1 border-l border-slate-200 pl-3 first:border-l-0 first:pl-0"
            >
              <h2 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {section.title}
              </h2>
              <div className="flex gap-1">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-1 px-2 py-1.5 rounded text-xs whitespace-nowrap ${
                        isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                      }`
                    }
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h2 className="text-2xl font-bold text-slate-900">{title}</h2>
      {subtitle && <p className="text-sm text-slate-600 mt-1">{subtitle}</p>}
    </div>
  );
}

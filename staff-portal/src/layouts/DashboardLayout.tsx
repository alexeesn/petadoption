import { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/applications', label: 'Applications', icon: '📋' },
  { to: '/pets', label: 'Pets', icon: '🐾' },
  { to: '/adopters', label: 'Adopters', icon: '👤' },
  { to: '/documents', label: 'Documents', icon: '📄' },
  { to: '/reviews', label: 'Reviews', icon: '✅' },
  { to: '/health', label: 'Health Records', icon: '🩺' },
  { to: '/adoptions', label: 'Adoption Records', icon: '🏠' },
  { to: '/packages', label: 'Packages', icon: '📦' },
  { to: '/payments', label: 'Payments', icon: '💳' },
  { to: '/reports', label: 'Reports', icon: '📈' },
  { to: '/notifications', label: 'Notifications', icon: '🔔' },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const visibleNavItems = [
    ...navItems,
    ...(user?.role === 'admin' ? [{ to: '/audit', label: 'Audit Logs', icon: '🔒' }] : []),
  ];

  return (
    <div className="min-h-screen bg-slate-100 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex-shrink-0 hidden md:flex flex-col">
        <div className="px-5 py-4 border-b border-slate-700">
          <h1 className="text-lg font-bold">Pet Adoption</h1>
          <p className="text-xs text-slate-400">Staff Portal</p>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-3 overflow-y-auto">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
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

      {/* Mobile top nav */}
      <div className="flex flex-col flex-1 min-w-0 md:hidden">
        <header className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold">Staff Portal</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-300">{user?.full_name}</span>
            <button onClick={handleLogout} className="text-xs text-red-400 focus:outline-none">
              Logout
            </button>
          </div>
        </header>
        <nav className="bg-white border-b border-slate-200 px-2 py-2 flex gap-1 overflow-x-auto">
          {visibleNavItems.map((item) => (
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
        </nav>
        <main className="flex-1 p-4">{children}</main>
      </div>

      {/* Desktop main content */}
      <main className="flex-1 p-6 hidden md:block">{children}</main>
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

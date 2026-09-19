import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
import { Icon, Logo } from '../components/Icons'
import type { IconName } from '../components/Icons'

// Adopter-facing navigation: browsing, applications, profile. Deliberately
// no dashboard — this is a pet adoption site, not an admin panel.
const navItems: { to: string; label: string; icon: IconName }[] = [
  { to: '/pets', label: 'Browse Pets', icon: 'search' },
  { to: '/applications', label: 'My Applications', icon: 'clipboard' },
  { to: '/profile', label: 'My Profile', icon: 'user' },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const { unreadCount } = useNotifications()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  const initial = (user?.first_name || user?.email || '?').trim().charAt(0).toUpperCase()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-stone-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link to="/" aria-label="Pawnscape home">
            <Logo />
          </Link>

          {/* Section tabs (desktop) */}
          <nav className="hidden items-center gap-1 md:flex" aria-label="Adopter navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/pets'}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors ${
                    isActive ? 'bg-primary-900 text-white' : 'text-stone-600 hover:bg-stone-100 hover:text-primary-900'
                  }`
                }
              >
                <Icon name={item.icon} className="h-[18px] w-[18px]" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-stone-500 lg:block">Hi, {user?.first_name || user?.email}</span>
            <Link
              to="/notifications"
              className="relative flex h-10 w-10 items-center justify-center rounded-full text-stone-600 transition-colors hover:bg-stone-100 hover:text-primary-900"
              aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : 'Notifications'}
            >
              <Icon name="bell" className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute right-0.5 top-0.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-accent-400 px-1 text-[10px] font-bold text-primary-900 ring-2 ring-white">
                  {unreadCount}
                </span>
              )}
            </Link>
            <span
              className="hidden h-9 w-9 items-center justify-center rounded-full bg-primary-100 font-display text-sm font-bold text-primary-800 sm:flex"
              aria-hidden="true"
            >
              {initial}
            </span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-md px-2 py-2 text-sm font-medium text-stone-600 transition-colors hover:text-primary-900"
            >
              <Icon name="logout" className="h-[18px] w-[18px]" />
              <span>Logout</span>
            </button>
          </div>
        </div>

        {/* Section tabs (mobile) */}
        <nav className="flex gap-1 overflow-x-auto border-t border-stone-100 px-3 py-2 md:hidden" aria-label="Adopter navigation (mobile)">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/pets'}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-primary-900 text-white' : 'text-stone-600'
                }`
              }
            >
              <Icon name={item.icon} className="h-4 w-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}

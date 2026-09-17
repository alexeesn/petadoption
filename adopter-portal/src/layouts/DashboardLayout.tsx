import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'

// Adopter-facing navigation: browsing, applications, profile. Deliberately
// no dashboard — this is a pet adoption site, not an admin panel.
const navItems = [
  { to: '/pets', label: 'Browse Pets', icon: '🐶' },
  { to: '/applications', label: 'My Applications', icon: '📋' },
  { to: '/profile', label: 'My Profile', icon: '👤' },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const { unreadCount } = useNotifications()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen flex flex-col bg-orange-50">
      <header className="bg-white shadow-sm border-b border-orange-100 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden="true">🐾</span>
            <span className="text-xl font-bold text-orange-600">Pawnscape</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-stone-500 hidden sm:block">
              Hi, {user?.first_name || user?.email}
            </span>
            <Link
              to="/notifications"
              className="relative text-lg text-stone-600 hover:text-orange-600"
              aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : 'Notifications'}
            >
              <span aria-hidden="true">🔔</span>
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold bg-red-500 text-white rounded-full">
                  {unreadCount}
                </span>
              )}
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm font-medium text-stone-600 hover:text-orange-600"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 gap-6">
        <nav className="md:w-56 shrink-0" aria-label="Adopter navigation">
          <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-2 flex md:flex-col gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/pets'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive ? 'bg-orange-100 text-orange-700' : 'text-stone-600 hover:bg-stone-50'
                  }`
                }
              >
                <span aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </nav>

        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

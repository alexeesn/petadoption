import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/pets', label: 'Find a Pet' },
]

export default function PublicLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white shadow-sm border-b border-orange-100 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden="true">🐾</span>
            <span className="text-xl font-bold text-orange-600">Pawnscape</span>
          </Link>
          <nav className="flex items-center gap-6" aria-label="Main">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${isActive ? 'text-orange-600' : 'text-stone-600 hover:text-orange-600'}`
                }
              >
                {link.label}
              </NavLink>
            ))}
            {user ? (
              <div className="flex items-center gap-4">
                <Link
                  to="/applications"
                  className="text-sm font-medium text-stone-600 hover:text-orange-600"
                >
                  My Applications
                </Link>
                <button
                  onClick={() => logout()}
                  className="text-sm font-medium text-stone-600 hover:text-orange-600"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <Link
                  to="/login"
                  className="text-sm font-medium text-stone-600 hover:text-orange-600"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center px-4 py-2 bg-orange-600 text-white text-sm font-medium rounded-md hover:bg-orange-700"
                >
                  Get Started
                </Link>
              </div>
            )}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-orange-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xl" aria-hidden="true">🐾</span>
              <span className="font-semibold text-stone-700">Pawnscape Pet Adoption</span>
            </div>
            <p className="text-sm text-stone-500">
              Helping pets find loving homes.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

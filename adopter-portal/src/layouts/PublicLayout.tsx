import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Logo, PawMark } from '../components/Icons'

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/pets', label: 'Find a Pet' },
]

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `relative py-1 text-sm font-medium transition-colors ${
    isActive
      ? 'text-primary-900 after:absolute after:inset-x-0 after:-bottom-1 after:h-[3px] after:rounded-full after:bg-accent-400'
      : 'text-stone-600 hover:text-primary-900'
  }`

export default function PublicLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-stone-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link to="/" aria-label="Pawnscape home">
            <Logo />
          </Link>
          <nav className="flex items-center gap-5 sm:gap-7" aria-label="Main">
            {navLinks.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.to === '/'} className={navLinkClass}>
                {link.label}
              </NavLink>
            ))}
            {user ? (
              <div className="flex items-center gap-4">
                <Link to="/applications" className="text-sm font-medium text-stone-600 transition-colors hover:text-primary-900">
                  My Applications
                </Link>
                <button
                  onClick={() => logout()}
                  className="text-sm font-medium text-stone-600 transition-colors hover:text-primary-900"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3 sm:gap-4">
                <Link to="/login" className="text-sm font-medium text-stone-600 transition-colors hover:text-primary-900">
                  Log in
                </Link>
                <Link to="/register" className="btn btn-primary">
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

      <footer className="bg-primary-900 text-primary-100">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-accent-400 text-primary-900">
                <PawMark className="h-5 w-5" />
              </span>
              <span className="font-display font-semibold text-white">Pawnscape Pet Adoption</span>
            </div>
            <p className="text-sm text-primary-200">Helping pets find loving homes.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

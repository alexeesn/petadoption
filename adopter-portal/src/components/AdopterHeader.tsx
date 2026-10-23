import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Icon, Logo } from './Icons'
import NotificationBell from './NotificationBell'
import ThemeToggle from './ThemeToggle'

const links = [{ to: '/', label: 'Home' }, { to: '/pets', label: 'Find a Pet' }]
export default function AdopterHeader() {
  const { user, logout } = useAuth()
  const [panel, setPanel] = useState<'account' | 'notifications' | null>(null)
  const account = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const openedByHover = useRef(false)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  useEffect(() => { setPanel(null) }, [pathname, user?.id])
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (!account.current?.contains(event.target as Node)) setPanel(value => value === 'account' ? null : value) }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [])
  const navClass = ({ isActive }: { isActive: boolean }) => `adopter-nav-link ${isActive ? 'is-active' : ''}`
  return <header className="portal-header adopter-header sticky top-3 z-40">
    <div className="mx-auto flex h-[4.5rem] max-w-7xl items-center justify-between gap-2 px-3 sm:px-6 lg:px-8">
      <Link to="/" aria-label="PawConnect home"><Logo /></Link>
      <nav className="header-nav hidden md:flex" aria-label="Main">{links.map(link => <NavLink key={link.to} to={link.to} end={link.to === '/'} className={navClass}>{link.label}</NavLink>)}</nav>
      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
        {user ? <>
          <NotificationBell key={user.id} open={panel === 'notifications'} onOpenChange={open => setPanel(value => open ? 'notifications' : value === 'notifications' ? null : value)} />
          <div ref={account} className="relative" onPointerEnter={event => { if (event.pointerType === 'mouse' && panel !== 'account') { openedByHover.current = true; setPanel('account') } }} onPointerLeave={event => { if (event.pointerType === 'mouse' && !account.current?.contains(document.activeElement)) { openedByHover.current = false; setPanel(value => value === 'account' ? null : value) } }} onKeyDown={event => { if (event.key === 'Escape') { setPanel(null); trigger.current?.focus() } }}>
            <button ref={trigger} type="button" aria-label="Profile menu" aria-expanded={panel === 'account'} onClick={() => { if (openedByHover.current) { openedByHover.current = false; setPanel('account') } else setPanel(value => value === 'account' ? null : 'account') }} className="icon-button border-primary-200 bg-primary-50 text-primary-800"><Icon name="user" className="h-5 w-5" /></button>
            {panel === 'account' && <div className="absolute right-0 top-full z-50 w-64 pt-3">
              <nav className="popover-panel overflow-hidden p-2" aria-label="Account">
                <div className="mb-1 border-b border-stone-200 px-3 py-3"><p className="truncate text-sm font-bold text-stone-900">{user.first_name || user.full_name || 'Your account'}</p><p className="mt-1 truncate text-xs text-stone-500">{user.email}</p></div>
                {[['/applications', 'My Applications', 'clipboard'], ['/profile', 'My Profile', 'user'], ['/notifications', 'Notifications', 'bell']].map(([to, label, icon]) => <Link key={to} to={to} onClick={() => setPanel(null)} className="flex items-center gap-3 rounded-md px-3 py-3 text-sm text-stone-700 hover:bg-primary-50"><Icon name={icon} className="h-4 w-4"/>{label}</Link>)}
                <button type="button" className="mt-1 flex w-full items-center gap-3 border-t border-stone-200 px-3 py-3 text-left text-sm font-semibold text-red-700" onClick={async () => { setPanel(null); await logout(); navigate('/') }}><Icon name="logout" className="h-4 w-4"/>Logout</button>
              </nav>
            </div>}
          </div>
        </> : <>
          <Link to="/login" className="px-2 py-2 text-sm font-semibold text-stone-700">Log in</Link>
          <Link to="/register" className="btn btn-primary hidden sm:inline-flex">Get started</Link>
        </>}
      </div>
    </div>
    <nav className="flex justify-center gap-2 border-t border-stone-200 px-3 py-2 md:hidden" aria-label="Main (mobile)">{links.map(link => <NavLink key={link.to} to={link.to} end={link.to === '/'} className={navClass}>{link.label}</NavLink>)}</nav>
  </header>
}

import { Link, Outlet } from 'react-router-dom'
import AdopterHeader from '../components/AdopterHeader'
import { PawMark } from '../components/Icons'

export default function PublicLayout() {
  return <div className="portal-shell flex flex-col">
    <AdopterHeader />
    <main className="flex-1"><Outlet /></main>
    <footer className="mt-8 border-t border-stone-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col justify-between gap-6 px-4 py-10 sm:flex-row sm:items-center sm:px-6 lg:px-8">
        <div className="flex items-center gap-3"><span className="brand-mark h-10 w-10"><PawMark className="h-6 w-6" /></span><div><p className="font-display text-lg font-bold text-primary-900">PawConnect</p><p className="mt-1 text-sm text-stone-500">A little connection. A lifelong companion.</p></div></div>
        <div className="flex gap-6 text-sm font-semibold text-stone-600"><Link to="/pets" className="hover:text-primary-700">Find a Pet</Link><Link to="/applications" className="hover:text-primary-700">Your adoption journey</Link></div>
      </div>
    </footer>
  </div>
}

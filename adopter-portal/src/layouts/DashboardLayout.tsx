import { Outlet } from 'react-router-dom'
import AdopterHeader from '../components/AdopterHeader'

export default function DashboardLayout() {
  return <div className="portal-shell flex flex-col">
    <AdopterHeader />
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-8"><Outlet /></main>
    <footer className="border-t border-stone-200 px-4 py-6 text-center text-xs text-stone-500">PawConnect · Every adoption starts with a connection.</footer>
  </div>
}

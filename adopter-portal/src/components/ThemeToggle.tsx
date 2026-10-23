import { useEffect, useState } from 'react'

const storageKey = 'pawconnect_adopter_theme'
function applyTheme(next: 'light' | 'dark') {
  const root = document.documentElement
  // Theme colors change together; hover transitions must not tween dark text
  // across an already-dark canvas during the switch.
  root.classList.add('theme-changing')
  root.dataset.theme = next
  root.classList.toggle('dark', next === 'dark')
  root.style.colorScheme = next
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-changing')))
}
function currentTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}
export default function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme)
  useEffect(() => {
    const update = () => {
      let saved: string | null = null
      try { saved = localStorage.getItem(storageKey) } catch { /* Browser storage can be unavailable. */ }
      const next = saved === 'dark' || saved === 'light' ? saved : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      applyTheme(next)
      setTheme(next)
    }
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    update()
    window.addEventListener('storage', update)
    media.addEventListener('change', update)
    return () => { window.removeEventListener('storage', update); media.removeEventListener('change', update) }
  }, [])
  function toggle() {
    const next = theme === 'light' ? 'dark' : 'light'
    applyTheme(next)
    setTheme(next)
    try { localStorage.setItem(storageKey, next) } catch { /* The current page still changes theme. */ }
  }
  return <button type="button" className="icon-button" onClick={toggle} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      {theme === 'light' ? <path d="M20.5 13A8.7 8.7 0 0 1 11 3.5 8.7 8.7 0 1 0 20.5 13Z" /> : <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>}
    </svg>
  </button>
}

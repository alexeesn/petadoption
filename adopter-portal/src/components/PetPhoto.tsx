import { useEffect, useState } from 'react'

/** An illustration is a placeholder, never a substitute photo of the pet. */
function PhotoPlaceholder({ name }: { name: string }) {
  return <div className="pet-photo-placeholder" role="img" aria-label={`Photo unavailable for ${name}`}>
    <svg viewBox="0 0 360 260" className="pet-placeholder-art" fill="none" aria-hidden="true">
      <ellipse cx="180" cy="220" rx="115" ry="10" fill="currentColor" opacity=".07" />
      <circle cx="180" cy="128" r="88" stroke="currentColor" opacity=".12" />
      <g stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M90 165v-38c0-27 16-43 40-43s40 16 40 43v38M91 112c-20-9-31 2-28 21l5 29c1 10 10 14 22 8M169 111c19-9 29 3 26 22l-6 27c-2 10-9 14-19 9" />
        <path d="M105 171c-13 10-18 24-18 43h86c0-19-4-33-18-43M117 137h1m24 0h1" />
        <path d="m125 153 6 4 6-4m-6 5v9m-9 0c5 5 13 5 18 0M107 212v-14m47 14v-14" />
        <path d="m225 114-5-30 29 16c8-1 15-1 23 0l26-16-5 30c8 11 11 24 8 35-4 17-18 29-41 29s-38-12-42-29c-3-12 0-24 7-35Z" />
        <path d="M235 132h1m42 0h1m-24 12 5 4 5-4m-5 5v9m-8 0c4 4 12 4 16 0m-31-10-23-4m23 12-23 4m69-12 23-4m-23 12 23 4M238 178c-8 12-12 24-12 36h69c0-13-4-27-13-36m11 36c25 0 34-12 27-27-4-8-15-8-18-1" />
        <path d="M167 65c-15-10-17-19-11-24 5-4 11-2 14 2 4-5 10-7 15-3 7 6 4 15-18 25Z" opacity=".6" />
      </g>
    </svg>
    <span className="photo-placeholder-caption">Photo coming soon</span>
  </div>
}

export default function PetPhoto({ src, name, className = '', eager = false }: { src?: string; name: string; className?: string; eager?: boolean }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => { setFailed(false) }, [src])
  if (!src || failed) return <div className={`h-full w-full ${className}`}><PhotoPlaceholder name={name} /></div>
  return <img src={src} alt={name} loading={eager ? 'eager' : 'lazy'} className={`h-full w-full object-cover ${className}`} onError={() => setFailed(true)} />
}

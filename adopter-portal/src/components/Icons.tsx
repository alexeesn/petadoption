import type { ReactNode } from 'react'

/** Filled paw print used in the logo and as a photo placeholder. */
export function PawMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="currentColor" aria-hidden="true" focusable="false">
      <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
      <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
      <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
      <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
      <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
    </svg>
  )
}

/** Brand lockup: ink tile with a tag-yellow paw, followed by the wordmark. */
export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-primary-900 text-accent-400">
        <PawMark className="h-5 w-5" />
      </span>
      <span className="font-display text-xl font-bold tracking-tight text-primary-900">Pawnscape</span>
    </span>
  )
}

const paths: Record<string, ReactNode> = {
  heart: <path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2z" />,
  shield: (
    <>
      <path d="M12 3.5 5 6v5.5c0 4.3 2.9 7.6 7 9 4.1-1.4 7-4.7 7-9V6l-7-2.5z" />
      <path d="m9 12 2.2 2.2L15.5 10" />
    </>
  ),
  route: (
    <>
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="6" r="2" />
      <path d="M8 18h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16" />
    </>
  ),
  bell: (
    <>
      <path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2h-15l1.5-2z" />
      <path d="M10 21a2 2 0 0 0 4 0" />
    </>
  ),
  clipboard: (
    <>
      <rect x="5" y="4.5" width="14" height="16.5" rx="2" />
      <path d="M9 4.5V3.8A.8.8 0 0 1 9.8 3h4.4a.8.8 0 0 1 .8.8v.7" />
      <path d="M8.5 11h7M8.5 15h4.5" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M5 20c.6-3.6 3.3-5.6 7-5.6s6.4 2 7 5.6" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6" />
      <path d="m20 20-4.2-4.2" />
    </>
  ),
  arrowLeft: <path d="M19 12H5m6-6-6 6 6 6" />,
  arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
  chevronLeft: <path d="m14.5 6-6 6 6 6" />,
  chevronRight: <path d="m9.5 6 6 6-6 6" />,
  logout: (
    <>
      <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
      <path d="M10 8l-4 4 4 4M6 12h10" />
    </>
  ),
  home: (
    <>
      <path d="M4 11 12 4l8 7" />
      <path d="M6 9.5V20h12V9.5" />
      <path d="M10 20v-5h4v5" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
}

export type IconName = keyof typeof paths

export function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  )
}

/**
 * Decorative collar tag for the home page hero. Purely visual (aria-hidden).
 * A strap runs across the top, a big yellow tag hangs from it, and a smaller
 * round tag rests against it for depth.
 */
export function CollarTagArt({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 480 460" className={className} aria-hidden="true" focusable="false">
      {/* strap */}
      <g transform="rotate(-9 240 70)">
        <rect x="-40" y="44" width="560" height="56" rx="12" fill="#1B2D54" />
        <line x1="-30" y1="72" x2="510" y2="72" stroke="#93AED6" strokeWidth="2.5" strokeDasharray="9 9" strokeLinecap="round" opacity="0.7" />
      </g>
      {/* small round tag behind */}
      <g transform="rotate(14 372 322)">
        <circle cx="372" cy="322" r="66" fill="#DCE6F4" stroke="#1C2438" strokeWidth="5" />
        <circle cx="372" cy="270" r="9" fill="#EEF2F7" stroke="#1C2438" strokeWidth="4" />
        <g transform="translate(346 300) scale(1.6)" fill="#2B4A82">
          <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
          <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
          <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
          <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
          <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
        </g>
      </g>
      {/* main tag */}
      <g transform="rotate(7 200 260)">
        <circle cx="200" cy="112" r="24" fill="none" stroke="#1C2438" strokeWidth="8" />
        <rect x="70" y="126" width="260" height="290" rx="96" fill="#FFC93C" stroke="#1C2438" strokeWidth="6" />
        <rect x="90" y="146" width="220" height="250" rx="78" fill="none" stroke="#1C2438" strokeWidth="3" strokeDasharray="3 10" strokeLinecap="round" opacity="0.45" />
        <circle cx="200" cy="176" r="12" fill="#EEF2F7" stroke="#1C2438" strokeWidth="5" />
        <g transform="translate(120 218) scale(5)" fill="#1C2438">
          <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
          <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
          <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
          <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
          <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
        </g>
      </g>
    </svg>
  )
}

import type { ReactNode } from 'react';

/** Filled paw print used in the logo. */
export function PawMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="currentColor" aria-hidden="true" focusable="false">
      <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
      <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
      <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
      <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
      <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
    </svg>
  );
}

const paths: Record<string, ReactNode> = {
  dashboard: (
    <>
      <rect x="4" y="4" width="7" height="8" rx="1.5" />
      <rect x="13" y="4" width="7" height="5" rx="1.5" />
      <rect x="13" y="11" width="7" height="9" rx="1.5" />
      <rect x="4" y="14" width="7" height="6" rx="1.5" />
    </>
  ),
  clipboard: (
    <>
      <rect x="5" y="4.5" width="14" height="16.5" rx="2" />
      <path d="M9 4.5V3.8A.8.8 0 0 1 9.8 3h4.4a.8.8 0 0 1 .8.8v.7" />
      <path d="M8.5 11h7M8.5 15h4.5" />
    </>
  ),
  calendar: (
    <>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2" />
      <path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M5 20c.6-3.6 3.3-5.6 7-5.6s6.4 2 7 5.6" />
    </>
  ),
  pulse: <path d="M3 12h4l2.5-6 4 12 2.5-6H21" />,
  home: (
    <>
      <path d="M4 11 12 4l8 7" />
      <path d="M6 9.5V20h12V9.5" />
      <path d="M10 20v-5h4v5" />
    </>
  ),
  card: (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="M3.5 10h17M7 15h3" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8 16v-4M12 16V8M16 16v-6" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="9.5" rx="2" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
    </>
  ),
  bell: (
    <>
      <path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2h-15l1.5-2z" />
      <path d="M10 21a2 2 0 0 0 4 0" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
      <path d="M10 8l-4 4 4 4M6 12h10" />
    </>
  ),
};

export type IconName = keyof typeof paths | 'paw';

export function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  if (name === 'paw') return <PawMark className={className} />;
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
  );
}

/** Small brand tile: ink square with a tag-yellow paw. */
export function BrandTile({ className = 'h-9 w-9' }: { className?: string }) {
  return (
    <span className={`flex items-center justify-center rounded-[11px] bg-primary-900 text-accent-400 ${className}`}>
      <PawMark className="h-[55%] w-[55%]" />
    </span>
  );
}

/** Decorative collar tag for the sign-in screen. Purely visual (aria-hidden). */
export function CollarTagArt({ className = '' }: { className?: string }) {
  const paw = (
    <>
      <ellipse cx="7.5" cy="14" rx="3" ry="4" transform="rotate(-20 7.5 14)" />
      <ellipse cx="13" cy="8.5" rx="3" ry="4.2" transform="rotate(-8 13 8.5)" />
      <ellipse cx="19.5" cy="8.5" rx="3" ry="4.2" transform="rotate(8 19.5 8.5)" />
      <ellipse cx="25" cy="14" rx="3" ry="4" transform="rotate(20 25 14)" />
      <path d="M16 15c-4.2 0-8 4.6-8 8.2 0 2.6 2 3.8 4 3.8 1.5 0 2.7-.6 4-.6s2.5.6 4 .6c2 0 4-1.2 4-3.8 0-3.6-3.8-8.2-8-8.2z" />
    </>
  );
  return (
    <svg viewBox="0 0 480 460" className={className} aria-hidden="true" focusable="false">
      <g transform="rotate(-9 240 70)">
        <rect x="-40" y="44" width="560" height="56" rx="12" fill="#2B4A82" />
        <line x1="-30" y1="72" x2="510" y2="72" stroke="#93AED6" strokeWidth="2.5" strokeDasharray="9 9" strokeLinecap="round" opacity="0.7" />
      </g>
      <g transform="rotate(14 372 322)">
        <circle cx="372" cy="322" r="66" fill="#DCE6F4" stroke="#0F1626" strokeWidth="5" />
        <circle cx="372" cy="270" r="9" fill="#141F3B" stroke="#0F1626" strokeWidth="4" />
        <g transform="translate(346 300) scale(1.6)" fill="#2B4A82">{paw}</g>
      </g>
      <g transform="rotate(7 200 260)">
        <circle cx="200" cy="112" r="24" fill="none" stroke="#DCE6F4" strokeWidth="8" />
        <rect x="70" y="126" width="260" height="290" rx="96" fill="#FFC93C" stroke="#0F1626" strokeWidth="6" />
        <rect x="90" y="146" width="220" height="250" rx="78" fill="none" stroke="#141F3B" strokeWidth="3" strokeDasharray="3 10" strokeLinecap="round" opacity="0.45" />
        <circle cx="200" cy="176" r="12" fill="#141F3B" stroke="#0F1626" strokeWidth="5" />
        <g transform="translate(120 218) scale(5)" fill="#141F3B">{paw}</g>
      </g>
    </svg>
  );
}

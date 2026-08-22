import { useTheme } from '../lib/theme'

/* Lucide-shaped glyphs, stroke 1.5, drawn on a 24 grid so they sit at
   the same optical weight as the wordmark. One icon family, no emoji. */

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4L7 17M17 7l1.4-1.4" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 14.4A8.4 8.4 0 0 1 9.6 4a8.4 8.4 0 1 0 10.4 10.4Z" />
    </svg>
  )
}

function SystemIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="12.5" rx="1.6" />
      <path d="M8.5 20.5h7M12 16.5v4" />
    </svg>
  )
}

const ICON = { system: SystemIcon, light: SunIcon, dark: MoonIcon }
const NEXT = { system: 'light', light: 'dark', dark: 'system' }
const SAYS = { system: 'match the system', light: 'light', dark: 'dark' }

export default function ThemeToggle() {
  const { pref, resolved, cycle } = useTheme()
  const Icon = ICON[pref]

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={cycle}
      /* Announce the current state AND what the press will do — an
         icon-only control with no label is unusable on a screen reader. */
      aria-label={`Theme: ${SAYS[pref]}${pref === 'system' ? ` (currently ${resolved})` : ''}. Switch to ${SAYS[NEXT[pref]]}.`}
      title={`Theme: ${SAYS[pref]}`}
    >
      <span className="theme-toggle-glyph" key={pref}>
        <Icon />
      </span>
    </button>
  )
}

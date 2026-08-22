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

/* Two states, two icons. The glyph shows the theme you are looking at;
   the label says what pressing it does. There is deliberately no
   "system" position — see the note in lib/theme.js. */
export default function ThemeToggle() {
  const { resolved, toggle } = useTheme()
  const dark = resolved === 'dark'
  const Icon = dark ? MoonIcon : SunIcon
  const next = dark ? 'light' : 'dark'

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      /* an icon-only control is unusable on a screen reader without this */
      aria-label={`${dark ? 'Dark' : 'Light'} theme. Switch to ${next}.`}
      title={`Switch to ${next} theme`}
    >
      <span className="theme-toggle-glyph" key={resolved}>
        <Icon />
      </span>
    </button>
  )
}

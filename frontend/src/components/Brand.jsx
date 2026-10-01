/* Sentio brand mark — gradient waveform "S" pulse */
export function SentioLogo({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-label="Sentio">
      <defs>
        <linearGradient id="sentio-g" x1="0" y1="0" x2="48" y2="48">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="50%" stopColor="#8b5cf6" />
          <stop offset="100%" stopColor="#ec4899" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill="url(#sentio-g)" />
      <path
        d="M10 30 L16 30 L20 18 L25 34 L29 24 L32 30 L38 30"
        stroke="white"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="38" cy="18" r="2.5" fill="white" opacity="0.9" />
    </svg>
  )
}

export function SentioWordmark({ size = 34, sub = "SOCIAL PULSE ANALYTICS" }) {
  return (
    <div className="flex items-center gap-3">
      <SentioLogo size={size} />
      <div className="leading-tight">
        <div className="font-bold tracking-tight brand-word text-lg">Sentio</div>
        {sub && <div className="text-[9px] tracking-[0.2em] opacity-60">{sub}</div>}
      </div>
    </div>
  )
}

/* ---- platform logos (inline SVG, official-ish marks) ---- */

export function RedditLogo({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#FF4500" aria-label="Reddit">
      <path d="M12 0C5.373 0 0 5.373 0 12c0 3.314 1.343 6.314 3.515 8.485l-2.286 2.286C.775 23.225 1.097 24 1.738 24H12c6.627 0 12-5.373 12-12S18.627 0 12 0Zm4.388 3.199c1.104 0 1.999.895 1.999 1.999 0 1.105-.895 2-1.999 2-.946 0-1.739-.657-1.947-1.539v.002c-1.147.162-2.032 1.15-2.032 2.341v.007c1.776.067 3.4.567 4.686 1.363.473-.363 1.064-.58 1.707-.58 1.547 0 2.802 1.254 2.802 2.802 0 1.117-.655 2.081-1.601 2.531-.088 3.256-3.637 5.876-7.997 5.876-4.361 0-7.905-2.617-7.998-5.87-.954-.447-1.614-1.415-1.614-2.538 0-1.548 1.255-2.802 2.803-2.802.645 0 1.239.218 1.712.585 1.275-.79 2.881-1.291 4.64-1.365v-.01c0-1.663 1.263-3.034 2.88-3.207.188-.911.993-1.595 1.959-1.595Zm-8.085 8.376c-.784 0-1.459.78-1.506 1.797-.047 1.016.64 1.429 1.426 1.429.786 0 1.371-.369 1.418-1.385.047-1.017-.553-1.841-1.338-1.841Zm7.406 0c-.786 0-1.385.824-1.338 1.841.047 1.017.634 1.385 1.418 1.385.785 0 1.473-.413 1.426-1.429-.046-1.017-.721-1.797-1.506-1.797Zm-3.703 4.013c-.974 0-1.907.048-2.77.135-.147.015-.241.168-.183.305.483 1.154 1.622 1.964 2.953 1.964 1.33 0 2.47-.81 2.953-1.964.057-.137-.037-.29-.184-.305-.863-.087-1.795-.135-2.769-.135Z"/>
    </svg>
  )
}

export function YouTubeLogo({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#FF0000" aria-label="YouTube">
      <path d="M23.5 6.2c-.3-1-1.1-1.8-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5c-1 .3-1.8 1.1-2.1 2.1C0 8.1 0 12 0 12s0 3.9.5 5.8c.3 1 1.1 1.8 2.1 2.1 1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5c1-.3 1.8-1.1 2.1-2.1.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.5 15.6V8.4L15.8 12l-6.3 3.6z"/>
    </svg>
  )
}

export function InstagramLogo({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-label="Instagram">
      <defs>
        <linearGradient id="ig-g" x1="0" y1="24" x2="24" y2="0">
          <stop offset="0%" stopColor="#FFD600"/>
          <stop offset="35%" stopColor="#FF7A00"/>
          <stop offset="60%" stopColor="#FF0069"/>
          <stop offset="90%" stopColor="#D300C5"/>
        </linearGradient>
      </defs>
      <rect width="24" height="24" rx="6" fill="url(#ig-g)"/>
      <rect x="4" y="4" width="16" height="16" rx="4.5" fill="none" stroke="white" strokeWidth="1.8"/>
      <circle cx="12" cy="12" r="3.6" fill="none" stroke="white" strokeWidth="1.8"/>
      <circle cx="16.8" cy="7.2" r="1.1" fill="white"/>
    </svg>
  )
}

export function FacebookLogo({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#1877F2" aria-label="Facebook">
      <path d="M24 12c0-6.6-5.4-12-12-12S0 5.4 0 12c0 6 4.4 11 10.1 11.9v-8.4H7.1V12h3V9.4c0-3 1.8-4.7 4.5-4.7 1.3 0 2.7.2 2.7.2v3h-1.5c-1.5 0-2 .9-2 1.9V12h3.4l-.5 3.5h-2.9v8.4C19.6 23 24 18 24 12z"/>
    </svg>
  )
}

export function XLogo({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-label="X">
      <path
        fill="currentColor"
        d="M18.9 1.2h3.7l-8.1 9.3L24 22.8h-7.5l-5.9-7.7-6.7 7.7H.2l8.7-9.9L0 1.2h7.7l5.3 7 6-7zm-1.3 19.4h2L6.6 3.3H4.4l13.2 17.3z"
      />
    </svg>
  )
}

export const PLATFORMS = [
  { id: "reddit", name: "Reddit", Logo: RedditLogo, color: "#FF4500" },
  { id: "youtube", name: "YouTube", Logo: YouTubeLogo, color: "#FF0000" },
  { id: "instagram", name: "Instagram", Logo: InstagramLogo, color: "#E1306C" },
  { id: "facebook", name: "Facebook", Logo: FacebookLogo, color: "#1877F2" },
  { id: "x", name: "X", Logo: XLogo, color: "currentColor" },
]

export function PlatformBadge({ source, size = 16 }) {
  const platform = PLATFORMS.find((p) => p.id === source)
  if (!platform) return <span className="platform-tag">{source}</span>
  const { Logo } = platform
  return (
    <span className="inline-flex items-center gap-1.5" title={platform.name}>
      <Logo size={size} />
      <span className="text-[10px] opacity-70">{platform.name}</span>
    </span>
  )
}

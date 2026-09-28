import { Link, NavLink, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../lib/auth"
import { useTheme } from "../lib/hooks"
import { SentioWordmark, PLATFORMS } from "./Brand"

/* ---- lucide-style stroke icons ---- */
const I = ({ d, size = 17, children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {d ? <path d={d} /> : children}
  </svg>
)
export const Icons = {
  dashboard: (p) => <I {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></I>,
  live: (p) => <I {...p} d="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />,
  analyze: (p) => <I {...p} d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />,
  trends: (p) => <I {...p} d="M22 7l-8.5 8.5-5-5L2 17M16 7h6v6" />,
  models: (p) => <I {...p} d="M3 3v18h18M18 17V9M13 17V5M8 17v-3" />,
  pipeline: (p) => <I {...p}><path d="M6 3v12" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="6" r="3" /><path d="M18 9a9 9 0 0 1-9 9" /></I>,
  sources: (p) => <I {...p}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" /></I>,
  settings: (p) => <I {...p}><path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3" /><path d="M14 2v4M8 10v4M16 18v4" /></I>,
  logout: (p) => <I {...p} d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />,
  moon: (p) => <I {...p} d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />,
  sun: (p) => <I {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></I>,
}

export function Card({ children, className = "", hover = false }) {
  return <section className={`card ${hover ? "card-hover" : ""} ${className}`}>{children}</section>
}

export function SectionTitle({ title, detail, right }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {detail && <p className="mt-0.5 text-xs" style={{ color: "var(--text-soft)" }}>{detail}</p>}
      </div>
      {right}
    </div>
  )
}

export function SentimentChip({ label }) {
  if (!label) return null
  return <span className={`sentiment-chip tag-${label}`}>{label}</span>
}

export function Skeleton({ h = 60, className = "" }) {
  return <div className={`skeleton ${className}`} style={{ height: h }} />
}

export function EmptyState({ text }) {
  return <div className="py-10 text-center text-xs" style={{ color: "var(--text-faint)" }}>{text}</div>
}

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: Icons.dashboard },
  { to: "/live", label: "Live Feed", icon: Icons.live },
  { to: "/analyze", label: "Analyze", icon: Icons.analyze },
  { to: "/trends", label: "Trends", icon: Icons.trends },
  { to: "/models", label: "Models", icon: Icons.models },
  { to: "/pipeline", label: "Pipeline", icon: Icons.pipeline },
  { to: "/sources", label: "Sources", icon: Icons.sources },
]

const TITLES = {
  "/dashboard": "Dashboard", "/live": "Live Feed", "/analyze": "Analyze",
  "/trends": "Trending", "/models": "Model Comparison", "/pipeline": "Pipeline Monitor",
  "/sources": "Data Sources", "/settings": "Settings",
}

function SideItem({ to, label, icon: Icon, onClick }) {
  return (
    <NavLink to={to} onClick={onClick} className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}>
      <span className="side-icon"><Icon /></span>
      <span>{label}</span>
    </NavLink>
  )
}

export function AppShell({ children }) {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const title = TITLES[pathname] || (pathname.startsWith("/analyze/") ? "Post Analysis" : "Sentio")

  return (
    <div className="app-frame">
      {/* sidebar */}
      <aside className="sidebar">
        <div className="sidebar-head">
          <Link to="/dashboard"><SentioWordmark size={30} sub={null} /></Link>
        </div>

        <nav className="sidebar-nav">
          <div className="side-section">Workspace</div>
          {NAV.slice(0, 4).map((item) => <SideItem key={item.to} {...item} />)}
          <div className="side-section">System</div>
          {NAV.slice(4).map((item) => <SideItem key={item.to} {...item} />)}
        </nav>

        <div className="sidebar-foot">
          <button className="side-link" onClick={() => navigate("/settings")}>
            <span className="side-icon"><Icons.settings /></span>
            <span>Settings</span>
          </button>
          <button className="side-link" onClick={toggle}>
            <span className="side-icon">{theme === "dark" ? <Icons.sun /> : <Icons.moon />}</span>
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
          <div className="user-card">
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
              style={{ background: "linear-gradient(135deg, var(--accent), var(--accent3))" }}
            >
              {(user?.name || "U")[0].toUpperCase()}
            </span>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-xs font-semibold">{user?.name || "You"}</div>
              <div className="truncate text-[10.5px]" style={{ color: "var(--text-faint)" }}>{user?.email}</div>
            </div>
            <button className="icon-btn" onClick={logout} title="Sign out"><Icons.logout size={15} /></button>
          </div>
        </div>
      </aside>

      {/* main column */}
      <div className="main-col">
        <header className="topbar">
          <h1 className="text-[15px] font-semibold tracking-tight">{title}</h1>
          <LiveStatusDot />
        </header>
        {/* mobile nav */}
        <nav className="mobile-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `mobile-link ${isActive ? "active" : ""}`}>
              <item.icon size={14} /> {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="page-area">{children}</main>
      </div>
    </div>
  )
}

function LiveStatusDot() {
  return (
    <span className="hidden items-center gap-2 rounded-full border px-3 py-1.5 sm:flex" style={{ borderColor: "var(--border)", background: "var(--chip)" }}>
      <span className="live-dot" />
      <span className="font-mono text-[10px] font-bold tracking-wider" style={{ color: "var(--positive)" }}>LIVE</span>
      <span className="flex items-center gap-1.5 border-l pl-2" style={{ borderColor: "var(--border)" }}>
        {PLATFORMS.map((p) => (
          <span key={p.id} title={p.name} className="opacity-80">{p.icon || <p.Logo size={12} />}</span>
        ))}
      </span>
    </span>
  )
}

export function PlatformFilter({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <button className={`chip ${!value ? "chip-active" : ""}`} onClick={() => onChange("")}>All</button>
      {PLATFORMS.map((p) => {
        const { Logo } = p
        return (
          <button key={p.id} className={`chip ${value === p.id ? "chip-active" : ""}`} onClick={() => onChange(p.id)}>
            <Logo size={12} /> {p.name}
          </button>
        )
      })}
    </div>
  )
}

export { PlatformBadge } from "./Brand"

import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../lib/auth"
import { SentioWordmark, PLATFORMS } from "./Brand"

export function Card({ children, className = "", hover = false }) {
  return <section className={`card ${hover ? "card-hover" : ""} ${className}`}>{children}</section>
}

export function SectionTitle({ title, detail, right }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-[15px] font-bold">{title}</h2>
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

const RAIL = [
  { to: "/dashboard", label: "Dash", icon: "▦" },
  { to: "/live", label: "Live", icon: "⚡" },
  { to: "/analyze", label: "Analyze", icon: "🔗" },
  { to: "/trends", label: "Trends", icon: "📈" },
  { to: "/models", label: "Models", icon: "⚖" },
  { to: "/pipeline", label: "Flow", icon: "_connected" },
  { to: "/sources", label: "Sources", icon: "◎" },
  { to: "/settings", label: "Settings", icon: "⚙" },
]

export function AppShell({ children, nav = [] }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <div className="min-h-screen">
      {/* top navbar */}
      <header
        className="sticky top-0 z-40 border-b backdrop-blur"
        style={{ borderColor: "var(--border)", background: "var(--nav-bg)" }}
      >
        <div className="mx-auto flex max-w-[1500px] items-center gap-5 px-5 py-3">
          <Link to="/dashboard" className="shrink-0">
            <SentioWordmark size={32} sub={null} />
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">
            {nav.map((item) => (
              <Link key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LiveStatusDot />
            <button
              className="flex items-center gap-2 rounded-full border py-1 pl-1 pr-3 transition hover:border-indigo-400"
              style={{ borderColor: "var(--border)" }}
              onClick={() => navigate("/settings")}
              title="Profile & settings"
            >
              <span
                className="flex size-7 items-center justify-center rounded-full text-[11px] font-bold text-white"
                style={{ background: "linear-gradient(135deg, var(--accent), var(--accent3))" }}
              >
                {(user?.name || "U")[0].toUpperCase()}
              </span>
              <span className="text-xs font-semibold">{user?.name?.split(" ")[0] || "You"}</span>
            </button>
            <button className="btn" onClick={logout} title="Logout">⎋</button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1500px] gap-4 px-4 py-4">
        {/* left rail */}
        <aside className="sticky top-[76px] hidden h-fit w-[76px] shrink-0 md:block">
          <div className="card flex flex-col items-center gap-1 p-2">
            {RAIL.map((item) => (
              <Link key={item.to} to={item.to} className={({ isActive }) => `rail-link w-full ${isActive ? "active" : ""}`}>
                <span className="text-base">{item.icon === "_connected" ? "⇄" : item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        </aside>

        {/* page content */}
        <main className="min-w-0 flex-1 pb-10">{children}</main>
      </div>
    </div>
  )
}

function LiveStatusDot() {
  return (
    <span className="hidden items-center gap-2 rounded-full border px-3 py-1.5 sm:flex" style={{ borderColor: "var(--border)" }}>
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

export const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/live", label: "Live Feed" },
  { to: "/analyze", label: "Analyze" },
  { to: "/trends", label: "Trends" },
  { to: "/models", label: "Models" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/sources", label: "Sources" },
]

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

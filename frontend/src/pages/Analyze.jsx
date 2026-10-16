import { useNavigate } from "react-router-dom"
import { fetchComments, fetchPosts, fetchAccounts } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, EmptyState } from "../components/UI"
import { PlatformBadge, PLATFORMS } from "../components/Brand"

const CAPABILITY = {
  reddit: "Full comment threads + account-level analysis (keyless)",
  youtube: "Video comments, channel-wide analysis + topic streams (keyless)",
  threads: "OAuth live monitoring — future scope (flow built, needs app creds)",
  instagram: "Paste comments now · account mode needs a Meta token",
  facebook: "Paste comments now · account mode needs a Meta token",
  x: "Single-post analysis + topic streams via public syndication",
}

const STATUS = {
  reddit: { dot: "var(--positive)", label: "Working · live" },
  youtube: { dot: "var(--positive)", label: "Working · live" },
  threads: { dot: "#3b82f6", label: "Future scope" },
  instagram: { dot: "#3b82f6", label: "Future scope" },
  facebook: { dot: "#3b82f6", label: "Future scope" },
  x: { dot: "var(--positive)", label: "Working · live" },
}

// row 1: the three fully-working platforms; row 2: Meta apps (future scope)
const WORKING = ["youtube", "reddit", "x"]
const FUTURE = ["instagram", "facebook", "threads"]

export default function Analyze() {
  const navigate = useNavigate()
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Analyze</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Pick a platform — analyze a single post, an entire account, or stream a trending topic live
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {WORKING.map((id) => {
          const p = PLATFORMS.find((x) => x.id === id)
          return <PlatformCard key={id} p={p} navigate={navigate} />
        })}
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[11px] font-bold tracking-wide" style={{ color: "var(--text-faint)" }}>META APPS · FUTURE SCOPE</span>
          <span className="h-px flex-1" style={{ background: "var(--border-soft)" }} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FUTURE.map((id) => {
            const p = PLATFORMS.find((x) => x.id === id)
            return <PlatformCard key={id} p={p} navigate={navigate} future />
          })}
        </div>
      </div>

      <RecentAccounts />
      <RecentPosts />
    </div>
  )
}

function PlatformCard({ p, navigate, future = false }) {
  const { Logo } = p
  const status = STATUS[p.id]
  return (
    <button
      onClick={() => navigate(`/analyze/${p.id}`)}
      className="card card-hover p-5 text-left"
      style={future ? { opacity: 0.75 } : undefined}
    >
      <div className="flex items-start justify-between">
        <span
          className="flex h-11 w-11 items-center justify-center rounded-xl"
          style={{ background: `${p.color === "currentColor" ? "#a1a1aa" : p.color}1f` }}
        >
          <Logo size={22} />
        </span>
        <span className="flex items-center gap-1.5 text-[10px] font-medium" style={{ color: "var(--text-soft)" }}>
          <span className="h-2 w-2 rounded-full" style={{ background: status.dot }} />
          {status.label}
        </span>
      </div>
      <div className="mt-3 font-bold tracking-tight">{p.name}</div>
      <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--text-soft)" }}>
        {CAPABILITY[p.id]}
      </p>
      <div className="mt-3 text-[11px] font-semibold" style={{ color: p.color !== "currentColor" ? p.color : "inherit" }}>
        {future ? "Setup guide →" : `Analyze ${p.name} →`}
      </div>
    </button>
  )
}

function RecentAccounts() {
  const accounts = usePolling(() => fetchAccounts(), [], 8000)
  const list = accounts.data?.accounts ?? []
  if (list.length === 0) return null
  return (
    <Card className="p-5">
      <SectionTitle title="Recently analyzed accounts" detail="Aggregate sentiment across every post of the account" />
      <div className="grid gap-2 sm:grid-cols-2">
        {list.slice(0, 4).map((a) => (
          <button
            key={a.account_key}
            onClick={() => (window.location.href = `/analyze/account/${a.platform}/${encodeURIComponent(a.handle)}`)}
            className="card card-hover p-3 text-left"
          >
            <div className="flex items-center gap-2">
              <PlatformBadge source={a.platform} size={13} />
              <span className="flex-1 text-xs font-semibold">@{a.handle}</span>
              <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                {a.posts_count} posts · {a.scored} scored
              </span>
            </div>
            {a.scored > 0 && (
              <div className="mt-2 flex h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                <div style={{ width: `${a.sentiment.positive_pct}%`, background: "var(--positive)" }} />
                <div style={{ width: `${a.sentiment.negative_pct}%`, background: "var(--negative)" }} />
                <div style={{ width: `${a.sentiment.neutral_pct}%`, background: "var(--neutral)" }} />
              </div>
            )}
          </button>
        ))}
      </div>
    </Card>
  )
}

function RecentPosts() {
  const posts = usePolling(() => fetchPosts(), [], 6000)
  const list = posts.data?.posts ?? []
  if (list.length === 0) return <EmptyState text="No analyses yet — pick a platform above to start" />
  return (
    <Card className="p-5">
      <SectionTitle title="Recently analyzed posts" detail="Click a post to inspect every comment" />
      <div className="grid gap-2 sm:grid-cols-2">
        {list.slice(0, 6).map((p) => (
          <button
            key={p.post_id}
            onClick={() => (window.location.href = `/analyze/post/${p.post_id}`)}
            className="card card-hover p-3 text-left"
          >
            <div className="flex items-center gap-2">
              <PlatformBadge source={p.source} size={13} />
              <span className="line-clamp-1 flex-1 text-xs font-semibold">{p.post_title}</span>
              <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{p.scored} scored</span>
            </div>
            {p.scored > 0 && (
              <div className="mt-2 flex h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                <div style={{ width: `${p.sentiment.positive_pct}%`, background: "var(--positive)" }} />
                <div style={{ width: `${p.sentiment.negative_pct}%`, background: "var(--negative)" }} />
                <div style={{ width: `${p.sentiment.neutral_pct}%`, background: "var(--neutral)" }} />
              </div>
            )}
          </button>
        ))}
      </div>
    </Card>
  )
}

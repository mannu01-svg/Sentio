import { useState } from "react"
import { Link } from "react-router-dom"
import { fetchHistory } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, EmptyState, Skeleton } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

const KIND_META = {
  post: { icon: "🔗", label: "Link" },
  account: { icon: "👤", label: "Account" },
  topic: { icon: "🔥", label: "Topic / Keyword" },
  keyword: { icon: "📝", label: "Pasted" },
}

const KIND_CHIPS = [
  { id: "", label: "All" },
  { id: "post", label: "🔗 Links" },
  { id: "account", label: "👤 Accounts" },
  { id: "topic", label: "🔥 Topics" },
  { id: "keyword", label: "📝 Pasted" },
]

function targetRoute(entry) {
  if (entry.kind === "account") return `/analyze/account/${entry.platform}/${encodeURIComponent(entry.handle || "")}`
  if (entry.kind === "topic") return `/topics/${entry.platform}/${encodeURIComponent(entry.keyword || "")}`
  if (entry.post_ids?.length === 1) return `/analyze/post/${entry.post_ids[0]}`
  return entry.post_ids?.length ? `/analyze/post/${entry.post_ids[0]}` : null
}

export default function History() {
  const [kind, setKind] = useState("")
  const state = usePolling(() => fetchHistory({ kind }), [kind], 8000)
  const entries = state.data?.history ?? []

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">History</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Every analysis you've ever run — links, accounts, keywords, topics, pasted comments — all saved, all viewable
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {KIND_CHIPS.map(({ id, label }) => (
          <button
            key={id || "all"}
            className={`chip ${kind === id ? "chip-active" : ""}`}
            onClick={() => setKind(id)}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          {entries.length} analyses · stored in PostgreSQL · survives restarts
        </span>
      </div>

      {!state.data ? (
        <div className="space-y-2">
          <Skeleton h={64} /><Skeleton h={64} /><Skeleton h={64} />
        </div>
      ) : entries.length === 0 ? (
        <Card className="p-10">
          <EmptyState text="No analyses yet — run one from the Analyze page and it will appear here forever." />
        </Card>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => {
            const meta = KIND_META[entry.kind] ?? KIND_META.post
            const route = targetRoute(entry)
            const s = entry.sentiment ?? {}
            return (
              <Card key={entry.id} hover className="p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg text-base" style={{ background: "var(--chip)" }}>
                    {meta.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="line-clamp-1 text-sm font-bold">{entry.title || entry.keyword || "Untitled analysis"}</span>
                      {entry.platform && <PlatformBadge source={entry.platform} size={12} />}
                      {entry.handle && <span className="chip !text-[10px]">@{entry.handle}</span>}
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
                      <span>{meta.label}</span>
                      <span>·</span>
                      <span>{entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}</span>
                      <span>·</span>
                      <span>{entry.scored > 0 ? `${entry.scored.toLocaleString()} comments scored` : "scoring pending…"}</span>
                    </div>
                  </div>
                  {entry.scored > 0 && (
                    <div className="flex w-32 shrink-0 flex-col gap-1">
                      <div className="flex h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                        <div style={{ width: `${s.positive_pct || 0}%`, background: "var(--positive)" }} />
                        <div style={{ width: `${s.negative_pct || 0}%`, background: "var(--negative)" }} />
                        <div style={{ width: `${s.neutral_pct || 0}%`, background: "var(--neutral)" }} />
                      </div>
                      <div className="flex gap-2 font-mono text-[9px]" style={{ color: "var(--text-faint)" }}>
                        <span style={{ color: "var(--positive)" }}>{s.positive_pct || 0}% pos</span>
                        <span style={{ color: "var(--negative)" }}>{s.negative_pct || 0}% neg</span>
                      </div>
                    </div>
                  )}
                  {route && (
                    <Link to={route} className="btn shrink-0 text-xs">
                      {entry.kind === "account" ? "👤 View account" : entry.kind === "topic" ? "🔥 Open stream" : "📊 View analysis"} →
                    </Link>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

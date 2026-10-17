import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { fetchComments, fetchTrends, fetchWords, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, EmptyState, Skeleton } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

const SOURCE_CHIPS = [
  { id: "", label: "All" },
  { id: "youtube", label: "YouTube" },
  { id: "x", label: "X" },
  { id: "reddit", label: "Reddit" },
]

export default function Trends() {
  const [params, setParams] = useSearchParams()
  const word = params.get("word") || ""

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Trends</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          What's rising right now — click any term to drill into its comments, or stream it live
        </p>
      </div>

      {word ? (
        <WordDrilldown word={word} onBack={() => setParams({})} />
      ) : (
        <TrendsOverview onSelect={(term) => setParams({ word: term })} />
      )}
    </div>
  )
}

function TrendsOverview({ onSelect }) {
  const [source, setSource] = useState("")
  const trends = usePolling(() => fetchTrends(14, source || undefined), [source], 8000)
  const words = usePolling(() => fetchWords(14), [], 8000)

  const hashtags = trends.data?.hashtags ?? []
  const velocity = trends.data?.words ?? []
  const frequent = words.data?.words ?? []
  const maxCount = frequent[0]?.count ?? 1
  const lookback = trends.data?.lookback_minutes ?? 60
  const lookbackLabel = lookback >= 1440 ? "last 24h vs previous 12h" : "recent 30 min vs previous 30 min"

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {SOURCE_CHIPS.map(({ id, label }) => (
          <button
            key={id || "all"}
            className={`chip ${source === id ? "chip-active" : ""}`}
            onClick={() => setSource(id)}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          auto-refreshes every 8s · {trends.data?.total_recent ?? 0} recent mentions
        </span>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-5">
          <SectionTitle title="Trending hashtags" detail={`Velocity: ${lookbackLabel}`} />
          {hashtags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {hashtags.map((h) => (
                <button key={h.term} className="chip !text-[12px]" onClick={() => onSelect(h.term)}>
                  {h.term}
                  <span style={{ color: "var(--positive)" }}>+{h.growth_pct}%</span>
                </button>
              ))}
            </div>
          ) : <EmptyState text="No hashtags yet — hashtag comments appear as the stream flows." />}
          <div className="mt-4 space-y-1.5">
            {velocity.slice(0, 7).map((w, i) => (
              <button
                key={w.term}
                onClick={() => onSelect(w.term)}
                className="grid w-full grid-cols-[24px_1fr_70px_60px] items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-indigo-500/10"
              >
                <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{String(i + 1).padStart(2, "0")}</span>
                <span className="min-w-0">
                  <span className="block truncate text-xs font-semibold">{w.term}</span>
                  <span className="mt-1 block h-1 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                    <span
                      className="block h-full rounded-full"
                      style={{ width: `${Math.max(Math.min(w.recent * 20, 100), 6)}%`, background: "linear-gradient(90deg, var(--accent), var(--accent2))" }}
                    />
                  </span>
                </span>
                <span className="text-right font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                  {w.recent} vs {w.previous}
                </span>
                <span className="text-right font-mono text-[11px] font-bold" style={{ color: w.growth_pct >= 0 ? "var(--positive)" : "var(--negative)" }}>
                  {w.growth_pct >= 0 ? "▲" : "▼"} {Math.abs(w.growth_pct)}%
                </span>
              </button>
            ))}
            {velocity.length === 0 && <Skeleton h={120} />}
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="Most frequent words" detail="Across all recent comments — click to drill down" />
          <div className="space-y-1.5">
            {frequent.map((w) => (
              <button
                key={w.word}
                onClick={() => onSelect(w.word)}
                className="grid w-full grid-cols-[110px_1fr_50px] items-center gap-3 rounded-lg px-2 py-1.5 text-left transition hover:bg-indigo-500/10"
              >
                <span className="truncate text-xs font-semibold">{w.word}</span>
                <span className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                  <span
                    className="block h-full rounded-full"
                    style={{ width: `${w.count * 100 / maxCount}%`, background: "linear-gradient(90deg, var(--accent), var(--accent2))" }}
                  />
                </span>
                <span className="text-right font-mono text-xs">{w.count}</span>
              </button>
            ))}
            {frequent.length === 0 && <Skeleton h={200} />}
          </div>
        </Card>
      </div>
    </div>
  )
}

function WordDrilldown({ word, onBack }) {
  const navigate = useNavigate()
  const [sentiment, setSentiment] = useState("")
  const state = usePolling(() => fetchComments({ limit: 100, q: word, sentiment }), [word, sentiment], 3000)
  const comments = state.data?.comments ?? []
  const counts = { positive: 0, negative: 0, neutral: 0 }
  comments.forEach((c) => { if (counts[c.llm_label] != null) counts[c.llm_label]++ })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn" onClick={onBack}>← All trends</button>
        <h2 className="text-lg font-extrabold">
          Comments using <span className="grad-text">"{word}"</span>
        </h2>
        <span className="chip">{comments.length} found</span>
        <div className="ml-auto flex gap-2">
          <button className="btn" onClick={() => navigate(`/topics/youtube/${encodeURIComponent(word)}`)}>
            🔴 Stream "{word}" live
          </button>
          <a className="btn" href={exportUrl({ q: word, sentiment })}>⬇ Export</a>
        </div>
      </div>

      <div className="flex gap-3">
        {Object.entries(counts).map(([label, n]) => (
          <button
            key={label}
            className={`card card-hover flex-1 px-4 py-3 ${sentiment === label ? "!border-indigo-400" : ""}`}
            onClick={() => setSentiment(sentiment === label ? "" : label)}
          >
            <div className="flex items-center justify-between">
              <SentimentChip label={label} />
              <span className="font-mono text-lg font-bold">{n}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="space-y-2.5">
        {comments.map((c) => (
          <Card key={c.id} hover className="p-4">
            <div className="flex items-center gap-3">
              <PlatformBadge source={c.source} />
              <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                {c.ts ? new Date(c.ts).toLocaleTimeString() : ""}
              </span>
              <span className="ml-auto"><SentimentChip label={c.llm_label} /></span>
            </div>
            <HighlightedText text={c.text} word={word} />
          </Card>
        ))}
        {comments.length === 0 && <Card className="p-10"><EmptyState text={`No comments found containing "${word}".`} /></Card>}
      </div>
    </div>
  )
}

function HighlightedText({ text, word }) {
  if (!word) return <p className="mt-2 text-[13px] leading-relaxed">{text}</p>
  const parts = text.split(new RegExp(`(${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"))
  return (
    <p className="mt-2 text-[13px] leading-relaxed">
      {parts.map((part, i) =>
        part.toLowerCase() === word.toLowerCase() ? (
          <mark key={i} className="rounded bg-indigo-500/25 px-1 text-indigo-300">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </p>
  )
}

import { useState } from "react"
import { fetchComments, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, PlatformFilter, EmptyState } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

export default function Live() {
  const [source, setSource] = useState("")
  const [sentiment, setSentiment] = useState("")
  const [q, setQ] = useState("")
  const filters = { source, sentiment, q }

  const feed = usePolling(() => fetchComments({ limit: 40, ...filters }), [source, sentiment, q], 2500)

  const comments = feed.data?.comments ?? []
  const counts = { positive: 0, negative: 0, neutral: 0 }
  comments.forEach((c) => { if (counts[c.llm_label] != null) counts[c.llm_label]++ })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Live Feed</h1>
          <p className="text-xs" style={{ color: "var(--text-soft)" }}>Scored comments streaming from the pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn" onClick={() => feed.setPaused(!feed.paused)}>
            {feed.paused ? "▶ Resume" : "⏸ Pause"}
          </button>
          <a className="btn" href={exportUrl(filters)}>⬇ Export</a>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[260px] flex-1"><PlatformFilter value={source} onChange={setSource} /></div>
          <select className="select w-[150px]" value={sentiment} onChange={(e) => setSentiment(e.target.value)}>
            <option value="">All sentiments</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
            <option value="neutral">Neutral</option>
          </select>
          <input className="input w-[200px]" placeholder="Search text…" value={q} onChange={(e) => setQ(e.target.value)} />
          {(source || sentiment || q) && (
            <button className="chip" onClick={() => { setSource(""); setSentiment(""); setQ("") }}>✕ clear filters</button>
          )}
          <span className="ml-auto flex items-center gap-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            <span className={feed.paused ? "live-dot" : ""} style={!feed.paused ? { width: 8, height: 8, borderRadius: "50%", background: "var(--positive)" } : { width: 8, height: 8, borderRadius: "50%", background: "var(--neutral)" }} />
            {feed.paused ? "paused" : `live · updated ${feed.lastUpdated?.toLocaleTimeString() ?? "—"}`}
          </span>
        </div>
      </Card>

      <div className="flex gap-3">
        {Object.entries(counts).map(([label, n]) => (
          <Card key={label} hover className="flex-1 px-4 py-3">
            <div className="flex items-center justify-between">
              <SentimentChip label={label} />
              <span className="font-mono text-lg font-bold">{n}</span>
            </div>
          </Card>
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
              <span className="ml-auto flex items-center gap-2">
                <SentimentChip label={c.llm_label} />
                <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                  {c.llm_score != null ? Number(c.llm_score).toFixed(2) : ""}
                </span>
              </span>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed">{c.text}</p>
            <div className="mt-2 flex items-center gap-4 font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
              <span>LLM · cardiffnlp tweet-RoBERTa</span>
              {c.post_id && <span className="rounded px-1.5 py-0.5" style={{ background: "var(--chip)" }}>post: {c.post_id}</span>}
            </div>
          </Card>
        ))}
        {feed.data && comments.length === 0 && (
          <Card className="p-10"><EmptyState text="No comments match the filters." /></Card>
        )}
        {!feed.data && <Card className="p-10"><EmptyState text="Connecting to the stream…" /></Card>}
      </div>
    </div>
  )
}

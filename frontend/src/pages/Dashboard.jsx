import { Link, useNavigate } from "react-router-dom"
import { useState } from "react"
import {
  Line, LineChart, Pie, PieChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts"
import {
  fetchAlerts, fetchComments, fetchPipeline, fetchSummary, fetchTimeline, fetchTrending,
  fetchStreamStatus, startLiveStream, stopLiveStream,
} from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, Skeleton, EmptyState } from "../components/UI"
import { PlatformBadge, PLATFORMS } from "../components/Brand"

const tooltipStyle = {
  backgroundColor: "var(--panel-solid)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  fontSize: 12,
  color: "var(--text)",
}

function Kpi({ label, value, tone, sub, delay = 0 }) {
  return (
    <Card hover className="p-5">
      <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>{label}</div>
      <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: tone }}>{value}</div>
      {sub && <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>{sub}</div>}
    </Card>
  )
}

export default function Dashboard() {
  const summary = usePolling(fetchSummary)
  const timeline = usePolling(() => fetchTimeline(90))
  const alerts = usePolling(fetchAlerts, [], 8000)
  const pipeline = usePolling(fetchPipeline, [], 6000)
  const feed = usePolling(() => fetchComments({ limit: 60 }), [], 4000)
  const trending = usePolling(() => fetchTrending(), [], 12000)
  const stream = usePolling(fetchStreamStatus, [], 3000)

  const s = summary.data?.sentiment ?? {}
  // round-robin interleave sources so one batch (e.g. threads) can't flood the whole card
  const feedRows = feed.data?.comments ?? []
  const bySource = {}
  feedRows.forEach((c) => { (bySource[c.source] ??= []).push(c) })
  const mixedFeed = []
  let added = true
  while (mixedFeed.length < 18 && added) {
    added = false
    for (const rows of Object.values(bySource)) {
      if (rows.length) { mixedFeed.push(rows.shift()); added = true }
      if (mixedFeed.length >= 18) break
    }
  }
  const windows = (timeline.data?.windows ?? []).map((w) => ({
    time: new Date(w.window_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    Positive: w.pos_pct, Negative: w.neg_pct, Neutral: w.neu_pct,
  }))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Dashboard</h1>
          <p className="text-xs" style={{ color: "var(--text-soft)" }}>Your social pulse at a glance</p>
        </div>
        <div className="flex items-center gap-2">
          <GoLiveButton stream={stream.data} />
          <Link to="/analyze" className="btn btn-primary">🔗 Analyze a post</Link>
        </div>
      </div>

      {alerts.data?.alert && (
        <Card className="border-red-500/40 p-4" style={{}}>
          <div className="flex items-center gap-3">
            <span className="relative flex size-3 shrink-0">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-60" />
              <span className="relative inline-flex size-2.5 rounded-full bg-red-400" />
            </span>
            <div>
              <div className="text-sm font-bold text-red-400">Negative sentiment spike detected</div>
              <p className="text-xs" style={{ color: "var(--text-soft)" }}>{alerts.data.message}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Kpi label="Comments processed" value={(summary.data?.total ?? 0).toLocaleString()} tone="var(--accent)" sub={`flow: ${pipeline.data?.flow_per_min ?? 0}/min · live LLM-scored`} />
        <Kpi label="Positive" value={`${s.positive_pct ?? 0}%`} tone="var(--positive)" sub={`${(s.positive ?? 0).toLocaleString()} comments · LLM`} />
        <Kpi label="Negative" value={`${s.negative_pct ?? 0}%`} tone="var(--negative)" sub={`${(s.negative ?? 0).toLocaleString()} comments · LLM`} />
        <Kpi label="Neutral" value={`${s.neutral_pct ?? 0}%`} tone="var(--neutral)" sub={`${(s.neutral ?? 0).toLocaleString()} comments · LLM`} />
      </div>

      <TrendingTopics data={trending.data} />

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <Card className="p-5">
          <SectionTitle title="Sentiment over time" detail="Share of comments per 1-minute window (LLM-scored)" />
          {timeline.data ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={windows} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-soft)" strokeDasharray="3 5" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: "var(--text-faint)", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-faint)", fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
                  <Line type="monotone" dataKey="Positive" stroke="var(--positive)" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="Negative" stroke="var(--negative)" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="Neutral" stroke="var(--neutral)" strokeWidth={2} dot={false} strokeDasharray="4 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <Skeleton h={256} />}
        </Card>

        <Card className="p-5">
          <SectionTitle title="Distribution" detail="All processed comments · scored by the tweet-trained LLM" />
          {summary.data ? (
            <div className="relative mx-auto h-56 w-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      { name: "Positive", value: s.positive ?? 0, color: "var(--positive)" },
                      { name: "Negative", value: s.negative ?? 0, color: "var(--negative)" },
                      { name: "Neutral", value: s.neutral ?? 0, color: "var(--neutral)" },
                    ].filter((d) => d.value > 0)}
                    dataKey="value" nameKey="name" innerRadius="68%" outerRadius="92%" paddingAngle={3} strokeWidth={0}
                  >
                    {[
                      { color: "var(--positive)" },
                      { color: "var(--negative)" },
                      { color: "var(--neutral)" },
                    ].map((c, i) => <Cell key={i} fill={c.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-mono text-2xl font-extrabold">{(summary.data.total ?? 0).toLocaleString()}</span>
                <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>comments</span>
              </div>
            </div>
          ) : <Skeleton h={224} />}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Card className="p-5">
          <SectionTitle
            title="Latest scored comments"
            detail="Straight from the Spark stream"
            right={<Link to="/live" className="text-xs font-semibold" style={{ color: "var(--accent)" }}>Open live feed →</Link>}
          />
          <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
            {mixedFeed.map((c) => (
              <div key={c.id} className="flex items-center gap-3 rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <PlatformBadge source={c.source} size={13} />
                    <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                      {c.ts ? new Date(c.ts).toLocaleTimeString() : ""}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-1 text-xs">{c.text}</p>
                </div>
                <SentimentChip label={c.llm_label} />
              </div>
            ))}
            {feed.data && feed.data.comments.length === 0 && <EmptyState text="Waiting for scored comments…" />}
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="Pipeline flow" detail="What's streaming right now" right={<Link to="/pipeline" className="text-xs font-semibold" style={{ color: "var(--accent)" }}>Details →</Link>} />
          <div className="space-y-2.5">
            {(pipeline.data?.stages ?? []).slice(0, 4).map((st) => (
              <div key={st.name} className="flex items-center justify-between rounded-xl border px-3 py-2.5" style={{ borderColor: "var(--border-soft)" }}>
                <div>
                  <div className="text-xs font-semibold">{st.name}</div>
                  <div className="text-[10px]" style={{ color: "var(--text-faint)" }}>{st.detail}</div>
                </div>
                <div className="font-mono text-sm font-bold" style={{ color: "var(--accent)" }}>
                  {st.value != null ? st.value.toLocaleString() : "—"}
                  <span className="ml-1 text-[9px] font-normal" style={{ color: "var(--text-faint)" }}>{st.unit}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

const TRENDING_SOURCES = [
  { id: "youtube", name: "YouTube", hint: "real-time search + comments" },
  { id: "x", name: "X (Twitter)", hint: "topic-matched live batch" },
  { id: "reddit", name: "Reddit", hint: "topic-matched live batch" },
]

function TrendingTopics({ data }) {
  const navigate = useNavigate()
  const [starting, setStarting] = useState(null)
  const [error, setError] = useState(null)

  const startStream = async (source, topic) => {
    if (starting) return
    setStarting(`${source}:${topic}`); setError(null)
    try {
      const res = await fetch("/api/topics/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, source, limit: 100 }),
      }).then((r) => r.json())
      if (res.status === "error") setError(res.message)
      else navigate(`/topics/${encodeURIComponent(source)}/${encodeURIComponent(topic)}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(null)
    }
  }

  return (
    <Card className="p-5">
      <SectionTitle
        title="Trending topics"
        detail="Top keywords per platform over every stored comment — click one for a real-time sentiment stream"
      />
      {error && <p className="mb-2 text-xs text-red-400">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-3">
        {TRENDING_SOURCES.map(({ id, name, hint }) => {
          const meta = PLATFORMS.find((p) => p.id === id)
          const topics = data?.trending?.[id] ?? []
          const totalComments = data?.trending?.[`${id}_comments`] ?? 0
          const Logo = meta?.Logo
          return (
            <div key={id}>
              <div className="mb-2 flex items-center gap-2">
                {Logo && <Logo size={14} />}
                <span className="text-xs font-bold">{name}</span>
                <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
                  {totalComments > 0 ? `${totalComments.toLocaleString()} comments scanned` : hint}
                </span>
              </div>
              {topics.length === 0 ? (
                <p className="text-[11px]" style={{ color: "var(--text-faint)" }}>Building topic list…</p>
              ) : (
                <div className="space-y-1.5">
                  {topics.slice(0, 6).map((t, i) => {
                    const key = `${id}:${t.topic}`
                    const isStarting = starting === key
                    const maxCount = topics[0]?.count ?? 1
                    return (
                      <button
                        key={t.topic}
                        onClick={() => startStream(id, t.topic)}
                        disabled={!!starting}
                        className="group flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors hover:bg-white/5 disabled:opacity-60"
                        style={{ borderColor: "var(--border-soft)" }}
                      >
                        <span className="w-4 font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{i + 1}</span>
                        <span className="min-w-0 flex-1">
                          <span className="line-clamp-1 block text-xs font-semibold">{t.topic}</span>
                          <span className="mt-1 block h-1 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                            <span
                              className="block h-full rounded-full"
                              style={{ width: `${Math.max((t.count * 100) / maxCount, 4)}%`, background: "linear-gradient(90deg, var(--accent), var(--accent2))" }}
                            />
                          </span>
                        </span>
                        <span className="shrink-0 text-right">
                          <span className="block font-mono text-[11px] font-bold">{t.count.toLocaleString()}</span>
                          <span className="block font-mono text-[9px]" style={{ color: "var(--text-faint)" }}>{t.share_pct}% of {id === "youtube" ? "YT" : id === "x" ? "X" : "r"}</span>
                        </span>
                        <span className="shrink-0 text-[10px] opacity-0 transition-opacity group-hover:opacity-100" style={{ color: "var(--accent)" }}>
                          {isStarting ? "…" : "▶ stream"}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-[10px]" style={{ color: "var(--text-faint)" }}>
        Counts are real mentions across every stored comment (recent mentions score 2×).
        YouTube topics pull fresh videos + comments live via yt-dlp search; X/Reddit topics stream
        topic-matched comments through the live replay pool — all scored by Kafka → Spark in ~30–60s.
      </p>
    </Card>
  )
}

function GoLiveButton({ stream }) {
  const [busy, setBusy] = useState(false)
  const live = stream?.live
  const secondsLeft = stream?.seconds_left ?? 0

  const toggle = async () => {
    setBusy(true)
    try {
      if (live) await stopLiveStream()
      else await startLiveStream({ minutes: 3, rate: 40 })
    } finally {
      setBusy(false)
    }
  }

  if (!stream) return <div className="h-9 w-32 animate-pulse rounded-lg" style={{ background: "var(--border-soft)" }} />

  if (live) {
    return (
      <button
        onClick={toggle}
        disabled={busy}
        className="flex items-center gap-2 rounded-lg border px-4 py-2 text-xs font-bold transition-colors disabled:opacity-70"
        style={{ borderColor: "var(--positive)", background: "color-mix(in srgb, var(--positive) 12%, transparent)", color: "var(--positive)" }}
      >
        <span className="relative flex size-2.5">
          <span className="absolute inline-flex size-full animate-ping rounded-full opacity-60" style={{ background: "var(--positive)" }} />
          <span className="relative inline-flex size-2 rounded-full" style={{ background: "var(--positive)" }} />
        </span>
        LIVE · {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
        <span className="text-[10px] font-medium opacity-70">stop</span>
      </button>
    )
  }

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className="flex items-center gap-2 rounded-lg border px-4 py-2 text-xs font-bold transition-colors hover:bg-white/5 disabled:opacity-70"
      style={{ borderColor: "var(--border)" }}
    >
      <span className="text-sm">🔴</span>
      Go live
      <span className="text-[10px] font-medium" style={{ color: "var(--text-faint)" }}>3 min · 40/s</span>
    </button>
  )
}

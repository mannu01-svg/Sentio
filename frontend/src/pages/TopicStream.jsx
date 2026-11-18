import { useMemo, useState, useEffect } from "react"
import { Link, useParams } from "react-router-dom"
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"
import { fetchComments, fetchTopicStreams, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, EmptyState, Skeleton } from "../components/UI"
import { PlatformBadge, PLATFORMS } from "../components/Brand"

const STREAM_STAGES = [
  { icon: "📡", msg: "Pulling fresh comments about this topic…" },
  { icon: "📨", msg: "Publishing the batch to Kafka…" },
  { icon: "⚡", msg: "Spark is cleaning and parsing every comment…" },
  { icon: "🧠", msg: "LLM scoring in progress — sarcasm, slang, emoji, all of it…" },
  { icon: "💾", msg: "Scores landing in PostgreSQL…" },
  { icon: "📊", msg: "Charts are next — almost there…" },
]

function StreamLoader() {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setStage((s) => (s + 1) % STREAM_STAGES.length), 2600)
    return () => clearInterval(timer)
  }, [])
  const current = STREAM_STAGES[stage]
  return (
    <Card className="p-10">
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="relative flex size-14 items-center justify-center">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500/20" />
          <span className="relative text-3xl">{current.icon}</span>
        </span>
        <div>
          <div className="text-sm font-bold">{current.msg}</div>
          <p className="mt-1 text-xs" style={{ color: "var(--text-soft)" }}>
            The live stream scores comments the moment Spark processes them — usually 30–60s for the first batch.
          </p>
        </div>
        <div className="flex items-center gap-1.5" aria-hidden="true">
          {STREAM_STAGES.map((_, i) => (
            <span
              key={i}
              className="h-1.5 rounded-full transition-all duration-500"
              style={{
                width: i === stage ? 22 : 8,
                background: i <= stage ? "var(--positive)" : "var(--border-soft)",
              }}
            />
          ))}
        </div>
      </div>
    </Card>
  )
}

export default function TopicStream() {
  const { source, topic } = useParams()
  const decodedTopic = decodeURIComponent(topic || "")
  const meta = PLATFORMS.find((p) => p.id === source)

  const streams = usePolling(() => fetchTopicStreams(), [], 5000)
  // the stream record for this topic (history-driven; survives restarts).
  // keyword match covers youtube topic streams whose posts carry real video ids
  // instead of topic-<source>-<slug> ids.
  const stream = useMemo(() => {
    const all = streams.data?.streams ?? []
    const lower = decodedTopic.toLowerCase()
    return all.find((s) => s.source === source && (s.topic || "").toLowerCase() === lower)
      ?? all.find((s) => s.source === source && (s.topic || "").toLowerCase().includes(lower))
  }, [streams.data, source, decodedTopic])

  const postIds = stream?.posts ?? []
  const topicPosts = useMemo(
    () => (stream ? postIds.map((id, i) => ({
      post_id: id,
      post_title: stream.topic || decodedTopic,
      source,
      scored: stream.scored,
      sentiment: stream.sentiment ?? { positive_pct: 0, negative_pct: 0, neutral_pct: 0 },
      _first: i === 0,
    })) : []),
    [stream, postIds, source, decodedTopic]
  )

  const comments = usePolling(
    () => Promise.all(
      topicPosts.slice(0, 5).map((p) => fetchComments({ limit: 200, post_id: p.post_id }))
    ).then((rs) => rs.flatMap((r) => r.comments ?? [])),
    [postIds],
    3000
  )
  const list = comments.data ?? []

  const counts = { positive: 0, negative: 0, neutral: 0 }
  list.forEach((c) => { if (counts[c.llm_label] != null) counts[c.llm_label]++ })
  const total = list.length

  // live per-minute velocity: comments scored in the last minute
  const freshCount = list.filter(
    (c) => c.ts && Date.now() - new Date(c.ts).getTime() < 120_000
  ).length

  const chartData = [
    { name: "Positive", value: counts.positive, fill: "var(--positive)" },
    { name: "Negative", value: counts.negative, fill: "var(--negative)" },
    { name: "Neutral", value: counts.neutral, fill: "var(--neutral)" },
  ]

  const [sort, setSort] = useState("time")
  const sorted = useMemo(() => {
    const arr = [...list]
    if (sort === "score") arr.sort((a, b) => (a.llm_score ?? 0) - (b.llm_score ?? 0))
    else arr.sort((a, b) => (b.ts ?? "").localeCompare(a.ts ?? ""))
    return arr
  }, [list, sort])

  if (!meta) return <EmptyState text={`Unknown platform "${source}"`} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl" style={{ background: `${meta.color === "currentColor" ? "#a1a1aa" : meta.color}1f` }}>
              <meta.Logo size={18} />
            </span>
            <h1 className="text-xl font-extrabold">#{decodedTopic}</h1>
            <PlatformBadge source={source} size={12} />
          </div>
          <p className="mt-0.5 flex items-center gap-2 text-xs" style={{ color: "var(--text-soft)" }}>
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-emerald-400" />
            </span>
            Live topic stream — {total} comments scored {freshCount > 0 && `· ${freshCount} fresh`} · updating every 3s
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn"
            onClick={() => window.location.reload()}
            title="pull another batch of comments for this topic"
          >🔄 Refresh batch</button>
          {postIds.length > 0 && <a className="btn" href={exportUrl({ post_id: topicPosts[0]?.post_id })}>⬇ Export</a>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>Scored</div>
          <div className="count-in mt-1 font-mono text-2xl font-extrabold">{total}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>Positive</div>
          <div className="count-in mt-1 font-mono text-2xl font-extrabold" style={{ color: "var(--positive)" }}>
            {total ? Math.round(counts.positive * 100 / total) : 0}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>Negative</div>
          <div className="count-in mt-1 font-mono text-2xl font-extrabold" style={{ color: "var(--negative)" }}>
            {total ? Math.round(counts.negative * 100 / total) : 0}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>Neutral</div>
          <div className="count-in mt-1 font-mono text-2xl font-extrabold" style={{ color: "var(--neutral)" }}>
            {total ? Math.round(counts.neutral * 100 / total) : 0}%
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.6fr]">
        <Card className="p-4">
          <SectionTitle title="Sentiment split" detail="Live LLM-scored counts for this topic" />
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: "var(--text-faint)", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--text-faint)", fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: "var(--border-soft)" }}
                  contentStyle={{ background: "var(--panel-solid)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between p-4 pb-2">
            <SectionTitle title="Live comment stream" detail="Scored the moment Spark processes them" />
            <div className="flex gap-1.5">
              <button className={`chip ${sort === "time" ? "chip-active" : ""}`} onClick={() => setSort("time")}>🕒 Latest</button>
              <button className={`chip ${sort === "score" ? "chip-active" : ""}`} onClick={() => setSort("score")}>📉 Worst first</button>
            </div>
          </div>
          {comments.data == null ? (
            <div className="px-4 pb-4"><StreamLoader /></div>
          ) : list.length === 0 ? (
            <div className="px-4 pb-4"><StreamLoader /></div>
          ) : (
            <div className="max-h-[420px] space-y-2 overflow-y-auto px-4 pb-4">
              {sorted.slice(0, 120).map((c) => (
                <div key={c.id} className="flex items-start gap-3 rounded-xl border p-2.5" style={{ borderColor: "var(--border-soft)" }}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
                      <span>@{c.author}</span>
                      <span>{c.ts ? new Date(c.ts).toLocaleTimeString() : ""}</span>
                    </div>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed">{c.text}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <SentimentChip label={c.llm_label} />
                    <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                      {c.llm_score != null ? Number(c.llm_score).toFixed(2) : "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {topicPosts.length > 0 && (
        <Card className="p-5">
          <SectionTitle title="Source posts" detail="Where these comments came from" />
          <div className="grid gap-2 sm:grid-cols-2">
            {topicPosts.slice(0, 6).map((p) => (
              <Link
                key={p.post_id}
                to={`/analyze/post/${p.post_id}`}
                className="card card-hover p-3"
              >
                <div className="flex items-center gap-2">
                  <PlatformBadge source={p.source} size={12} />
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
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

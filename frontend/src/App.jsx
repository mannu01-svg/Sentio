import { useEffect, useMemo, useState } from "react"
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"
import { fetchComments, fetchCompare, fetchSummary, fetchTimeline, fetchWords } from "./api"

const COLORS = {
  positive: "#34d399",
  negative: "#f87171",
  neutral: "#94a3b8",
  accent: "#818cf8",
}
const REFRESH_MS = 3000

function usePolling(fn, deps = [], interval = REFRESH_MS) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () =>
      fn()
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e) => alive && setError(e.message))
    tick()
    const id = setInterval(tick, interval)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, error }
}

function Card({ children, className = "" }) {
  return (
    <section className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg shadow-black/20 ${className}`}>
      {children}
    </section>
  )
}

function SectionTitle({ title, detail, right }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
        {detail && <p className="mt-0.5 text-xs text-slate-400">{detail}</p>}
      </div>
      {right}
    </div>
  )
}

function SentimentBadge({ label }) {
  if (!label) return null
  const styles = {
    positive: "text-emerald-300 border-emerald-500/30 bg-emerald-500/10",
    negative: "text-rose-300 border-rose-500/30 bg-rose-500/10",
    neutral: "text-slate-300 border-slate-500/30 bg-slate-500/10",
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${styles[label] ?? styles.neutral}`}>
      <span className="size-1 rounded-full bg-current" />
      {label}
    </span>
  )
}

const chartAxis = { fill: "#64748b", fontSize: 10 }
const tooltipStyle = {
  backgroundColor: "#0f172a",
  border: "1px solid #334155",
  borderRadius: 8,
  fontSize: 12,
  color: "#e2e8f0",
}

function KpiCards({ summary }) {
  const s = summary?.sentiment ?? {}
  const cards = [
    { label: "Comments processed", value: (summary?.total ?? 0).toLocaleString(), tone: "text-indigo-300" },
    { label: "Positive", value: `${s.positive_pct ?? 0}%`, tone: "text-emerald-300", sub: `${s.positive ?? 0} comments` },
    { label: "Negative", value: `${s.negative_pct ?? 0}%`, tone: "text-rose-300", sub: `${s.negative ?? 0} comments` },
    { label: "Neutral", value: `${s.neutral_pct ?? 0}%`, tone: "text-slate-300", sub: `${s.neutral ?? 0} comments` },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <div className="text-xs text-slate-400">{c.label}</div>
          <div className={`mt-2 font-mono text-3xl font-semibold ${c.tone}`}>{c.value}</div>
          {c.sub && <div className="mt-1 text-[11px] text-slate-500">{c.sub}</div>}
        </Card>
      ))}
    </div>
  )
}

function TimelineChart({ windows }) {
  const data = (windows ?? []).map((w) => ({
    time: new Date(w.window_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    Positive: w.pos_pct,
    Negative: w.neg_pct,
    Neutral: w.neu_pct,
  }))
  return (
    <Card>
      <SectionTitle title="Sentiment over time" detail="Share of comments per 1-minute window (VADER)" />
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="time" tick={chartAxis} axisLine={false} tickLine={false} />
            <YAxis tick={chartAxis} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
            <Line type="monotone" dataKey="Positive" stroke={COLORS.positive} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Negative" stroke={COLORS.negative} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Neutral" stroke={COLORS.neutral} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function DistributionDonut({ summary }) {
  const s = summary?.sentiment ?? {}
  const data = [
    { name: "Positive", value: s.positive ?? 0, color: COLORS.positive },
    { name: "Negative", value: s.negative ?? 0, color: COLORS.negative },
    { name: "Neutral", value: s.neutral ?? 0, color: COLORS.neutral },
  ].filter((d) => d.value > 0)
  const total = data.reduce((acc, d) => acc + d.value, 0)
  return (
    <Card>
      <SectionTitle title="Sentiment distribution" detail="All processed comments" />
      <div className="relative mx-auto h-56 w-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="68%" outerRadius="92%" paddingAngle={3} strokeWidth={0}>
              {data.map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-semibold text-slate-100">{total.toLocaleString()}</span>
          <span className="text-[10px] text-slate-400">comments</span>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {data.map((d) => (
          <div key={d.name} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-slate-400">
              <span className="size-2 rounded-full" style={{ backgroundColor: d.color }} />{d.name}
            </span>
            <span className="font-mono text-slate-200">{total ? Math.round(d.value * 100 / total) : 0}%</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

function TopWords({ words }) {
  const data = (words ?? []).map((w) => ({ word: w.word, count: w.count }))
  return (
    <Card>
      <SectionTitle title="Trending words" detail="Frequency across recent comments (stopwords removed)" />
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 5" horizontal={false} />
            <XAxis type="number" tick={chartAxis} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="word" width={90} tick={chartAxis} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="count" fill={COLORS.accent} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function ComparePanel({ compare }) {
  if (!compare || compare.compared === 0) return null
  const agree = compare.agreement_pct ?? 0
  return (
    <Card>
      <SectionTitle
        title="Model comparison — VADER vs DistilBERT"
        detail="How often the lexicon method and the transformer agree"
        right={
          <span className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] text-indigo-300">
            AI vs classic NLP
          </span>
        }
      />
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <div className="text-[10px] text-slate-400">Agreement</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-indigo-300">{agree}%</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <div className="text-[10px] text-slate-400">Compared</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-slate-100">{compare.compared.toLocaleString()}</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <div className="text-[10px] text-slate-400">Label accuracy (VADER)</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-emerald-300">
            {compare.label_accuracy_vader_pct != null ? `${compare.label_accuracy_vader_pct}%` : "—"}
          </div>
        </div>
      </div>
      {(compare.disagreement_examples ?? []).length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-[11px] font-medium text-slate-300">Disagreement examples</div>
          <div className="space-y-1.5">
            {compare.disagreement_examples.slice(0, 3).map((d, i) => (
              <div key={i} className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950/40 px-3 py-2 text-[11px]">
                <span className="line-clamp-1 flex-1 text-slate-300">"{d.text}"</span>
                <SentimentBadge label={d.vader} />
                <span className="text-slate-500">vs</span>
                <SentimentBadge label={d.bert} />
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

function LiveFeed({ filters }) {
  const { data } = usePolling(() => fetchComments({ limit: 25, ...filters }), [filters.source, filters.sentiment, filters.q])
  const comments = data?.comments ?? []
  return (
    <Card>
      <SectionTitle
        title="Live feed"
        detail="Scored comments arriving from the Spark stream"
        right={
          <span className="flex items-center gap-1.5 rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-emerald-400" />
            </span>
            <span className="font-mono text-[9px] font-semibold tracking-wider text-emerald-300">LIVE</span>
          </span>
        }
      />
      <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
        {comments.map((c) => (
          <div key={c.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="flex items-center gap-2 text-[10px] text-slate-400">
              <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">{c.source}</span>
              <span className="truncate">@{c.author}</span>
              <span className="ml-auto font-mono">{c.ts ? new Date(c.ts).toLocaleTimeString() : ""}</span>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-200">{c.text}</p>
            <div className="mt-2 flex items-center gap-2">
              <SentimentBadge label={c.vader_label} />
              {c.vader_score != null && (
                <span className="font-mono text-[10px] text-slate-500">vader {Number(c.vader_score).toFixed(2)}</span>
              )}
              {c.bert_label && (
                <>
                  <span className="text-slate-600">·</span>
                  <SentimentBadge label={c.bert_label} />
                  {c.bert_score != null && (
                    <span className="font-mono text-[10px] text-slate-500">bert {Number(c.bert_score).toFixed(2)}</span>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {comments.length === 0 && (
          <div className="py-10 text-center text-xs text-slate-500">
            Waiting for scored comments… start the producer and the Spark job.
          </div>
        )}
      </div>
    </Card>
  )
}

export default function App() {
  const summaryState = usePolling(fetchSummary)
  const timelineState = usePolling(() => fetchTimeline(90))
  const wordsState = usePolling(() => fetchWords(12))
  const compareState = usePolling(() => fetchCompare(1000), [], 10000)

  const [source, setSource] = useState("")
  const [sentiment, setSentiment] = useState("")
  const [q, setQ] = useState("")
  const filters = useMemo(() => ({ source, sentiment, q }), [source, sentiment, q])

  const error = summaryState.error && timelineState.error && wordsState.error
  const lastProcessed = summaryState.data?.last_processed

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-indigo-600 text-lg">📊</div>
          <div>
            <h1 className="text-sm font-semibold">Social Media Sentiment Analysis</h1>
            <p className="text-[11px] text-slate-400">Kafka · Spark Structured Streaming · VADER + DistilBERT</p>
          </div>
          <div className="ml-auto flex items-center gap-2 text-[11px] text-slate-400">
            {lastProcessed && <span className="font-mono">last: {new Date(lastProcessed).toLocaleTimeString()}</span>}
            <span className={`size-2 rounded-full ${error ? "bg-rose-400" : "bg-emerald-400"}`} />
            {error ? "API offline" : "Streaming"}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 px-6 py-6">
        {error && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <p className="text-xs text-amber-300">
              API unreachable — is the backend running? Start with <code className="font-mono">docker compose up -d</code>, then the Spark job, then <code className="font-mono">uvicorn api.main:app</code>.
            </p>
          </Card>
        )}

        <KpiCards summary={summaryState.data} />

        <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
          <TimelineChart windows={timelineState.data?.windows} />
          <DistributionDonut summary={summaryState.data} />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr]">
          <TopWords words={wordsState.data?.words} />
          <div className="space-y-4">
            <ComparePanel compare={compareState.data} />
            <Card>
              <SectionTitle title="Sources" detail="Comments processed per platform" />
              <div className="space-y-2">
                {Object.entries(summaryState.data?.sources ?? {}).map(([name, count]) => (
                  <div key={name} className="flex items-center justify-between text-xs">
                    <span className="capitalize text-slate-300">{name}</span>
                    <span className="font-mono text-slate-200">{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
          <LiveFeed filters={filters} />
          <Card>
            <SectionTitle title="Filters" detail="Applied to the live feed" />
            <div className="space-y-3">
              <div>
                <label className="text-[11px] text-slate-400">Source</label>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                >
                  <option value="">All sources</option>
                  <option value="reddit">Reddit</option>
                  <option value="youtube">YouTube</option>
                  <option value="instagram">Instagram</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-slate-400">Sentiment</label>
                <select
                  value={sentiment}
                  onChange={(e) => setSentiment(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                >
                  <option value="">All sentiments</option>
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                  <option value="neutral">Neutral</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-slate-400">Keyword search</label>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="e.g. battery, tutorial…"
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                />
              </div>
            </div>
          </Card>
        </div>

        <footer className="border-t border-slate-800 pt-4 text-center text-[11px] text-slate-500">
          College project · data streamed from datasets via Kafka, processed with Spark, scored with VADER + DistilBERT
        </footer>
      </main>
    </div>
  )
}

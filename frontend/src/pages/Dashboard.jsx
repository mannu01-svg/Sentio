import { Link } from "react-router-dom"
import {
  Line, LineChart, Pie, PieChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts"
import { fetchAlerts, fetchComments, fetchPipeline, fetchSummary, fetchTimeline } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, Skeleton, EmptyState } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

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
  const feed = usePolling(() => fetchComments({ limit: 6 }), [], 4000)

  const s = summary.data?.sentiment ?? {}
  const windows = (timeline.data?.windows ?? []).map((w) => ({
    time: new Date(w.window_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    Positive: w.pos_pct, Negative: w.neg_pct, Neutral: w.neu_pct,
  }))

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-extrabold">Dashboard</h1>
          <p className="text-xs" style={{ color: "var(--text-soft)" }}>Your social pulse at a glance</p>
        </div>
        <Link to="/analyze" className="btn btn-primary">🔗 Analyze a post</Link>
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
        <Kpi label="Comments processed" value={(summary.data?.total ?? 0).toLocaleString()} tone="var(--accent)" sub={`flow: ${pipeline.data?.flow_per_min ?? 0}/min`} />
        <Kpi label="Positive" value={`${s.positive_pct ?? 0}%`} tone="var(--positive)" sub={`${(s.positive ?? 0).toLocaleString()} comments`} />
        <Kpi label="Negative" value={`${s.negative_pct ?? 0}%`} tone="var(--negative)" sub={`${(s.negative ?? 0).toLocaleString()} comments`} />
        <Kpi label="Neutral" value={`${s.neutral_pct ?? 0}%`} tone="var(--neutral)" sub={`${(s.neutral ?? 0).toLocaleString()} comments`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <Card className="p-5">
          <SectionTitle title="Sentiment over time" detail="Share of comments per 1-minute window (VADER)" />
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
          <SectionTitle title="Distribution" detail="All processed comments" />
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
          <div className="space-y-2">
            {(feed.data?.comments ?? []).map((c) => (
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
                <SentimentChip label={c.vader_label} />
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

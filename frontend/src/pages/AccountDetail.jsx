import { useMemo, useState, useEffect } from "react"
import { Link, useParams } from "react-router-dom"
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts"
import { fetchAccounts, fetchPosts, fetchComments, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, EmptyState, Skeleton } from "../components/UI"
import { PlatformBadge, PLATFORMS } from "../components/Brand"

const LOAD_STAGES = [
  { icon: "📡", msg: "Gathering the account's comments…" },
  { icon: "⚡", msg: "Spark is processing the batch…" },
  { icon: "🧠", msg: "LLM scoring every comment…" },
  { icon: "📊", msg: "Aggregating the account's sentiment…" },
]

function AnalyzingLoader({ label }) {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setStage((s) => (s + 1) % LOAD_STAGES.length), 2600)
    return () => clearInterval(timer)
  }, [])
  const current = LOAD_STAGES[stage]
  return (
    <div className="flex flex-col items-center gap-4 py-10 text-center">
      <span className="relative flex size-14 items-center justify-center">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-indigo-500/20" />
        <span className="relative text-3xl">{current.icon}</span>
      </span>
      <div>
        <div className="text-sm font-bold">{current.msg}</div>
        <p className="mt-1 text-xs" style={{ color: "var(--text-soft)" }}>
          {label} travel through Kafka → Spark before scores appear — usually 30–60s.
        </p>
      </div>
      <div className="flex items-center gap-1.5" aria-hidden="true">
        {LOAD_STAGES.map((_, i) => (
          <span
            key={i}
            className="h-1.5 rounded-full transition-all duration-500"
            style={{
              width: i === stage ? 22 : 8,
              background: i <= stage ? "var(--accent)" : "var(--border-soft)",
            }}
          />
        ))}
      </div>
    </div>
  )
}

export default function AccountDetail() {
  const { platform, handle } = useParams()
  const accounts = usePolling(() => fetchAccounts(), [], 8000)
  const account = (accounts.data?.accounts ?? []).find(
    (a) => a.platform === platform && a.handle.toLowerCase() === (handle || "").toLowerCase()
  )

  const posts = usePolling(() => fetchPosts(), [], 6000)
  const accountPosts = useMemo(() => {
    const ids = new Set(account?.posts ?? [])
    return (posts.data?.posts ?? []).filter((p) => ids.has(p.post_id))
  }, [posts.data, account])

  const comments = usePolling(
    () => Promise.all(
      (account?.posts ?? []).map((id) => fetchComments({ limit: 100, post_id: id }))
    ).then((rs) => rs.flatMap((r) => r.comments ?? [])),
    [account?.posts?.join(",")],
    8000
  )
  const list = comments.data ?? []

  const counts = { positive: 0, negative: 0, neutral: 0 }
  list.forEach((c) => { if (counts[c.llm_label] != null) counts[c.llm_label]++ })
  const total = list.length
  const meta = PLATFORMS.find((p) => p.id === platform)

  if (!accounts.data) {
    return <div className="space-y-3"><Skeleton h={40} /><Skeleton h={120} /><Skeleton h={300} /></div>
  }
  if (!account) {
    return (
      <EmptyState
        text={`No analysis found for @${handle} on ${platform}. Run it from the Analyze hub first.`}
      />
    )
  }

  return (
    <div className="space-y-4">
      <Header platform={platform} handle={handle} meta={meta} account={account} total={total} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Posts analyzed" value={account.posts_count} />
        <StatCard label="Comments scored" value={total} mono />
        <StatCard label="Avg LLM score" value={account.avg_score ?? "—"} mono />
        <StatCard label="Negative share" value={`${account.sentiment.negative_pct}%`} color="var(--negative)" />
      </div>

      <Card className="p-4">
        <SectionTitle title="Sentiment split" detail="LLM-scored aggregate across every comment of the account" />
        <div className="flex h-3 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
          <div style={{ width: `${account.sentiment.positive_pct}%`, background: "var(--positive)" }} />
          <div style={{ width: `${account.sentiment.negative_pct}%`, background: "var(--negative)" }} />
          <div style={{ width: `${account.sentiment.neutral_pct}%`, background: "var(--neutral)" }} />
        </div>
        <div className="mt-2 flex gap-4 text-[11px]" style={{ color: "var(--text-soft)" }}>
          <span>🟢 {account.sentiment.positive} positive ({account.sentiment.positive_pct}%)</span>
          <span>🔴 {account.sentiment.negative} negative ({account.sentiment.negative_pct}%)</span>
          <span>⚪ {account.sentiment.neutral} neutral ({account.sentiment.neutral_pct}%)</span>
        </div>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <SentimentScatter comments={list} />
        <RankedPosts posts={accountPosts} />
      </div>

      <CommentTable comments={list} platform={platform} handle={handle} />
    </div>
  )
}

function Header({ platform, handle, meta, account, total }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="flex items-center gap-2">
          {meta && (
            <span className="flex h-9 w-9 items-center justify-center rounded-xl" style={{ background: `${meta.color}1f` }}>
              <meta.Logo size={18} />
            </span>
          )}
          <h1 className="text-xl font-extrabold">@{handle}</h1>
          <PlatformBadge source={platform} size={12} />
        </div>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-soft)" }}>
          Account-level sentiment · {account.posts_count} posts · {total} comments scored · updating live as Spark scores more
        </p>
      </div>
      <a className="btn" href={exportUrl({ post_id: account.posts.join(",") })}>⬇ Export</a>
    </div>
  )
}

function StatCard({ label, value, mono, color }) {
  return (
    <Card className="p-4">
      <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>{label}</div>
      <div className={`count-in mt-1 text-2xl font-extrabold ${mono ? "font-mono" : ""}`}
        style={color ? { color } : undefined}>
        {value ?? 0}
      </div>
    </Card>
  )
}

function SentimentScatter({ comments }) {
  const [hover, setHover] = useState(null)
  const data = comments
    .filter((c) => c.llm_score != null)
    .map((c, i) => ({
      i,
      score: Number(c.llm_score),
      text: (c.text || "").slice(0, 90),
      label: c.llm_label,
    }))

  return (
    <Card className="p-4">
      <SectionTitle title="Sentiment scatter" detail="Each dot = one comment, x = LLM confidence (0…1)" />
      <div className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: -20 }}>
            <XAxis type="number" dataKey="score" domain={[0, 1]} tick={{ fontSize: 10 }} stroke="var(--border)" />
            <YAxis type="number" dataKey="i" hide />
            <ZAxis range={[30, 30]} />
            <Tooltip
              content={({ payload }) => {
                if (!payload?.length) return null
                const d = payload[0].payload
                return (
                  <div className="card p-2 text-[11px]" style={{ maxWidth: 260 }}>
                    <div className="font-mono" style={{ color: "var(--text-soft)" }}>
                      {d.score.toFixed(2)} · {d.label}
                    </div>
                    <div className="mt-1 leading-snug">{d.text}</div>
                  </div>
                )
              }}
            />
            <Scatter data={data} onClick={(d) => setHover(d?.text)}>
              {data.map((d, i) => (
                <Cell key={i} fill={`var(--${d.label === "positive" ? "positive" : d.label === "negative" ? "negative" : "neutral"})`} fillOpacity={0.65} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {hover && <p className="mt-1 text-[11px]" style={{ color: "var(--text-soft)" }}>{hover}</p>}
    </Card>
  )
}

function RankedPosts({ posts }) {
  const ranked = [...posts].sort((a, b) => (b.sentiment.negative_pct || 0) - (a.sentiment.negative_pct || 0))
  if (ranked.length === 0) return null
  return (
    <Card className="p-4">
      <SectionTitle title="Most negative posts first" detail="Prioritize the conversations that need attention" />
      <div className="max-h-[240px] space-y-2 overflow-y-auto pr-1">
        {ranked.map((p) => (
          <Link
            key={p.post_id}
            to={`/analyze/post/${p.post_id}`}
            className="block rounded-lg border p-2.5 transition-colors hover:bg-white/5"
            style={{ borderColor: "var(--border-soft)" }}
          >
            <div className="flex items-center gap-2">
              <span className="line-clamp-1 flex-1 text-xs font-semibold">{p.post_title}</span>
              <span className="font-mono text-[10px] font-bold" style={{ color: "var(--negative)" }}>
                {p.sentiment.negative_pct}% neg
              </span>
            </div>
            <div className="mt-1.5 flex h-1 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
              <div style={{ width: `${p.sentiment.positive_pct}%`, background: "var(--positive)" }} />
              <div style={{ width: `${p.sentiment.negative_pct}%`, background: "var(--negative)" }} />
              <div style={{ width: `${p.sentiment.neutral_pct}%`, background: "var(--neutral)" }} />
            </div>
          </Link>
        ))}
      </div>
    </Card>
  )
}

function CommentTable({ comments, platform, handle }) {
  const [sort, setSort] = useState("time") // time | score
  const sorted = useMemo(() => {
    const arr = [...comments]
    if (sort === "score") arr.sort((a, b) => (a.llm_score ?? 0) - (b.llm_score ?? 0))
    else arr.sort((a, b) => (b.ts ?? "").localeCompare(a.ts ?? ""))
    return arr
  }, [comments, sort])

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between p-5 pb-3">
        <SectionTitle title="Every comment" detail={`All comments across @${handle}'s analyzed posts`} />
        <div className="flex gap-1.5">
          <button className={`chip ${sort === "time" ? "chip-active" : ""}`} onClick={() => setSort("time")}>🕒 Latest</button>
          <button className={`chip ${sort === "score" ? "chip-active" : ""}`} onClick={() => setSort("score")}>📉 Worst first</button>
        </div>
      </div>
      {comments.length === 0 ? (
        <div className="p-6">
          <AnalyzingLoader label={`@${handle}'s comments`} />
        </div>
      ) : (
        <div className="max-h-[560px] overflow-y-auto px-5 pb-5">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "48%" }}>Comment</th>
                <th>LLM ★</th>
                <th>VADER</th>
                <th>DistilBERT</th>
                <th style={{ textAlign: "right" }}>Score</th>
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 300).map((c) => (
                <tr key={c.id}>
                  <td>
                    <p className="text-[12.5px] leading-relaxed">{c.text}</p>
                    <div className="mt-1 flex items-center gap-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
                      <span>@{c.author}</span>
                      {c.post_id && <Link to={`/analyze/post/${c.post_id}`} className="underline decoration-dotted">post</Link>}
                    </div>
                  </td>
                  <td><SentimentChip label={c.llm_label} /></td>
                  <td><SentimentChip label={c.vader_label} /></td>
                  <td><SentimentChip label={c.bert_label} /></td>
                  <td style={{ textAlign: "right" }}>
                    <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                      {c.llm_score != null ? Number(c.llm_score).toFixed(2) : "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

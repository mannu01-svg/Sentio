import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { fetchComments, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, EmptyState } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

const LOAD_STAGES = [
  { icon: "📡", msg: "Fetching comments for this post…" },
  { icon: "📨", msg: "Publishing to Kafka · comments-raw…" },
  { icon: "⚡", msg: "Spark is cleaning the text…" },
  { icon: "🧠", msg: "LLM scoring every comment (cardiffnlp tweet-RoBERTa)…" },
  { icon: "💾", msg: "Storing scores in PostgreSQL…" },
  { icon: "📊", msg: "Almost there — building your charts…" },
]

function AnalyzingLoader({ scored }) {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setStage((s) => (s + 1) % LOAD_STAGES.length), 2600)
    return () => clearInterval(timer)
  }, [])
  const current = LOAD_STAGES[stage]
  return (
    <Card className="p-10">
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="relative flex size-14 items-center justify-center">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-indigo-500/20" />
          <span className="relative text-3xl">{current.icon}</span>
        </span>
        <div>
          <div className="text-sm font-bold">{current.msg}</div>
          <p className="mt-1 text-xs" style={{ color: "var(--text-soft)" }}>
            Comments travel through Kafka → Spark → PostgreSQL before scores appear — usually 30–60s.
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
        {scored > 0 && (
          <span className="chip">{scored} comments scored so far…</span>
        )}
      </div>
    </Card>
  )
}

export default function AnalyzeDetail() {
  const { postId } = useParams()
  const state = usePolling(() => fetchComments({ limit: 500, post_id: postId }), [postId], 3000)

  const comments = state.data?.comments ?? []
  const counts = { positive: 0, negative: 0, neutral: 0 }
  comments.forEach((c) => { if (counts[c.llm_label] != null) counts[c.llm_label]++ })
  const total = comments.length
  const title = comments[0]?.post_title || `Post ${postId}`
  const source = comments[0]?.source

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            {source && <PlatformBadge source={source} />}
            <h1 className="line-clamp-1 text-xl font-extrabold">{title}</h1>
          </div>
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-soft)" }}>
            {total} comments scored {total > 0 && comments.length < 100 && "· updating live as Spark scores more…"}
          </p>
        </div>
        <a className="btn" href={exportUrl({ post_id: postId })}>⬇ Export this post</a>
      </div>

      {total === 0 && !state.data ? (
        <AnalyzingLoader scored={0} />
      ) : total === 0 ? (
        <AnalyzingLoader scored={0} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="p-4">
              <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>Total scored</div>
              <div className="count-in mt-1 font-mono text-2xl font-extrabold">{total}</div>
            </Card>
            {Object.entries(counts).map(([label, n]) => (
              <Card key={label} className="p-4">
                <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>{label}</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="count-in font-mono text-2xl font-extrabold" style={{ color: `var(--${label})` }}>{n}</span>
                  <span className="text-xs" style={{ color: "var(--text-faint)" }}>{total ? Math.round(n * 100 / total) : 0}%</span>
                </div>
                <div className="mt-2 h-1 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                  <div style={{ width: `${total ? n * 100 / total : 0}%`, height: "100%", background: `var(--${label})` }} />
                </div>
              </Card>
            ))}
          </div>

          <Card className="overflow-hidden">
            <div className="p-5 pb-3"><SectionTitle title="Every comment" detail="LLM verdict + confidence per comment — VADER & DistilBERT in the export" /></div>
            <div className="max-h-[620px] overflow-y-auto px-5 pb-5">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: "58%" }}>Comment</th>
                    <th>LLM ★</th>
                    <th style={{ textAlign: "right" }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {comments.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <p className="text-[12.5px] leading-relaxed">{c.text}</p>
                        <div className="mt-1 flex items-center gap-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
                          <span>@{c.author}</span>
                          <span>{c.ts ? new Date(c.ts).toLocaleTimeString() : ""}</span>
                        </div>
                      </td>
                      <td><SentimentChip label={c.llm_label} /></td>
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
          </Card>
        </>
      )}
    </div>
  )
}

import { useParams } from "react-router-dom"
import { fetchComments, exportUrl } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, EmptyState, Skeleton } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

export default function AnalyzeDetail() {
  const { postId } = useParams()
  const state = usePolling(() => fetchComments({ limit: 500, post_id: postId }), [postId], 3000)

  const comments = state.data?.comments ?? []
  const counts = { positive: 0, negative: 0, neutral: 0 }
  comments.forEach((c) => { if (counts[c.vader_label] != null) counts[c.vader_label]++ })
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
        <div className="p-5 pb-3"><SectionTitle title="Every comment" detail="Individual sentiment per comment — click none, just read & filter" /></div>
        {comments.length === 0 && !state.data ? (
          <div className="space-y-2 p-5 pt-0">
            <Skeleton h={52} /><Skeleton h={52} /><Skeleton h={52} />
          </div>
        ) : comments.length === 0 ? (
          <EmptyState text="Scores will appear here as the stream processes this post (~30–60s)." />
        ) : (
          <div className="max-h-[620px] overflow-y-auto px-5 pb-5">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "55%" }}>Comment</th>
                  <th>VADER</th>
                  <th>DistilBERT</th>
                  <th style={{ textAlign: "right" }}>Scores</th>
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
                    <td><SentimentChip label={c.vader_label} /></td>
                    <td><SentimentChip label={c.bert_label} /></td>
                    <td style={{ textAlign: "right" }}>
                      <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                        {c.vader_score != null ? Number(c.vader_score).toFixed(2) : "—"} / {c.bert_score != null ? Number(c.bert_score).toFixed(2) : "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

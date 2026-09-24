import { useEffect, useState } from "react"
import { fetchComments, fetchPosts, fetchSummary } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, Skeleton, EmptyState } from "../components/UI"
import {
  PLATFORMS, RedditLogo, YouTubeLogo, InstagramLogo, FacebookLogo, XLogo,
} from "../components/Brand"

const DATASETS = [
  {
    source: "reddit", Logo: RedditLogo, name: "Reddit",
    dataset: "Twitter & Reddit Sentimental Analysis (cosmos98)",
    rows: 37149, labels: "positive / negative / neutral", connected: true,
  },
  {
    source: "youtube", Logo: YouTubeLogo, name: "YouTube",
    dataset: "YouTube Comments Dataset (atifaliak) + yt-dlp live fetch",
    rows: 18364, labels: "positive / neutral / negative", connected: true,
  },
  {
    source: "instagram", Logo: InstagramLogo, name: "Instagram",
    dataset: "CityNet IG Comments Sentiment (vrashad)",
    rows: 1301, labels: "negative / neutral / positive", connected: true,
  },
  {
    source: "facebook", Logo: FacebookLogo, name: "Facebook",
    dataset: "Social Media Sentiments Analysis (kashishparmar02)",
    rows: 231, labels: "mapped from 99 emotion labels", connected: true,
  },
  {
    source: "x", Logo: XLogo, name: "X (Twitter)",
    dataset: "Sentiment140 — 1.6M tweets (kazanova), 20k sample",
    rows: 20000, labels: "positive / negative", connected: true,
  },
]

export default function Sources() {
  const summary = usePolling(fetchSummary, [], 6000)
  const posts = usePolling(fetchPosts, [], 8000)
  const counts = summary.data?.sources ?? {}

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Sources</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Five platforms, Kaggle datasets + live link fetching — one pipeline
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {DATASETS.map((d) => {
          const { Logo } = d
          const count = counts[d.source] ?? 0
          return (
            <Card key={d.source} hover className="p-5">
              <div className="flex items-start justify-between">
                <span className="flex size-11 items-center justify-center rounded-xl" style={{ background: "var(--chip)" }}>
                  <Logo size={24} />
                </span>
                <span className="chip !cursor-default" style={{ color: "var(--positive)", borderColor: "var(--positive)" }}>
                  ● streaming
                </span>
              </div>
              <h3 className="mt-3 text-[15px] font-bold">{d.name}</h3>
              <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--text-faint)" }}>{d.dataset}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 border-t pt-3" style={{ borderColor: "var(--border-soft)" }}>
                <div>
                  <div className="text-[9px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Dataset rows</div>
                  <div className="font-mono text-sm font-bold">{d.rows.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Processed</div>
                  <div className="font-mono text-sm font-bold" style={{ color: "var(--accent)" }}>{count.toLocaleString()}</div>
                </div>
              </div>
              <div className="mt-2 text-[10px]" style={{ color: "var(--text-faint)" }}>Labels: {d.labels}</div>
            </Card>
          )
        })}
      </div>

      <Card className="p-5">
        <SectionTitle
          title="Kaggle datasets"
          detail="Pulled via kagglehub, cleaned to comment + label, streamed through Kafka"
        />
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr><th>Platform</th><th>Dataset</th><th style={{ textAlign: "right" }}>Rows</th><th>Labels</th></tr>
            </thead>
            <tbody>
              {DATASETS.map((d) => {
                const { Logo } = d
                return (
                  <tr key={d.source}>
                    <td><span className="inline-flex items-center gap-2"><Logo size={14} /> {d.name}</span></td>
                    <td className="text-[11px]">{d.dataset}</td>
                    <td className="text-right font-mono">{d.rows.toLocaleString()}</td>
                    <td className="text-[11px]">{d.labels}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {(posts.data?.posts ?? []).length > 0 && (
        <Card className="p-5">
          <SectionTitle title="Live-fetched posts" detail="Comments pulled from real URLs, scored in the same pipeline" />
          <div className="space-y-2">
            {posts.data.posts.slice(0, 8).map((p) => {
              const platform = PLATFORMS.find((x) => x.id === p.source)
              return (
                <div key={p.post_id} className="flex items-center gap-3 rounded-xl border px-4 py-3" style={{ borderColor: "var(--border-soft)" }}>
                  {platform && <platform.Logo size={16} />}
                  <span className="line-clamp-1 flex-1 text-xs font-semibold">{p.post_title}</span>
                  <span className="font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>
                    {p.scored}/{p.comments_fetched} scored
                  </span>
                  <span className="font-mono text-[11px] font-bold" style={{ color: "var(--accent)" }}>
                    {p.sentiment.positive_pct}% pos
                  </span>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}

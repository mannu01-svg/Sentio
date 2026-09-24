import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { analyzePost, fetchComments } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, PlatformFilter, EmptyState } from "../components/UI"
import { PlatformBadge } from "../components/Brand"

export default function Analyze() {
  const navigate = useNavigate()
  const [url, setUrl] = useState("")
  const [pasteMode, setPasteMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [limit, setLimit] = useState(100)

  const submit = async () => {
    if (!url.trim() || loading) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await analyzePost({ url, mode: pasteMode ? "paste" : "auto", limit })
      if (res.status === "error") setError(res.message)
      else {
        setResult(res)
        navigate(`/analyze/${res.post_id}`)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Analyze a post</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Fetch comments from a YouTube video, Reddit thread — or paste them — and score every single one
        </p>
      </div>

      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex gap-1.5">
            <button className={`chip ${!pasteMode ? "chip-active" : ""}`} onClick={() => setPasteMode(false)}>🔗 URL mode</button>
            <button className={`chip ${pasteMode ? "chip-active" : ""}`} onClick={() => setPasteMode(true)}>📝 Paste mode</button>
          </div>
          <select className="select w-[130px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            <option value={50}>50 comments</option>
            <option value={100}>100 comments</option>
            <option value={200}>200 comments</option>
            <option value={500}>500 comments</option>
          </select>
        </div>
        <textarea
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={pasteMode
            ? "Paste comments — one per line…"
            : "https://youtube.com/watch?v=…  or  https://reddit.com/r/…/comments/…"}
          rows={pasteMode ? 6 : 2}
          className="input w-full resize-y"
        />
        <div className="mt-3 flex items-center gap-3">
          <button className="btn btn-primary" onClick={submit} disabled={loading || !url.trim()}>
            {loading ? "Fetching & streaming…" : "🚀 Analyze"}
          </button>
          {error && <span className="text-xs text-red-400">{error}</span>}
          <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
            YouTube: yt-dlp · Reddit: PullPush · scores appear in ~30–60s
          </span>
        </div>
      </Card>

      {result && (
        <Card className="border-emerald-500/40 p-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-bold text-emerald-400">✓ {result.post_title}</span>
            <span style={{ color: "var(--text-faint)" }}>— {result.comments_published} comments pushed</span>
          </div>
        </Card>
      )}

      <AnalyzeHint />
    </div>
  )
}

function AnalyzeHint() {
  const posts = usePolling(() => fetch("/api/posts").then((r) => r.json()), [], 6000)
  const list = posts.data?.posts ?? []
  if (list.length === 0) return null
  return (
    <Card className="p-5">
      <SectionTitle title="Recently analyzed" detail="Click a post to inspect every comment" />
      <div className="grid gap-2 sm:grid-cols-2">
        {list.slice(0, 6).map((p) => (
          <button
            key={p.post_id}
            onClick={() => (window.location.href = `/analyze/${p.post_id}`)}
            className="card card-hover p-3 text-left"
          >
            <div className="flex items-center gap-2">
              <PlatformBadge source={p.source} size={13} />
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
          </button>
        ))}
      </div>
    </Card>
  )
}

import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  analyzePost, analyzeAccount, fetchThreadsStatus, threadsAuthUrl, keywordSearch,
} from "../lib/api"
import { Card, EmptyState } from "../components/UI"
import { PLATFORMS } from "../components/Brand"

const ACCOUNT_SUPPORTED = new Set(["youtube", "reddit", "threads"])
const KEYWORD_SUPPORTED = new Set(["youtube", "x", "reddit"])

const PLACEHOLDERS = {
  youtube: "https://youtube.com/watch?v=…  or  https://youtube.com/shorts/…",
  reddit: "https://reddit.com/r/…/comments/…",
  x: "https://x.com/user/status/123",
  threads: "https://www.threads.net/@you/post/…  (your own connected threads)",
  instagram: "Paste comments below (no public API)",
  facebook: "Paste comments below (no public API)",
}

const FUTURE_NOTES = {
  instagram: {
    what: "Paste-mode analysis works today; account-level analysis needs a Meta Graph API token.",
    demo: "Instagram comments flow through the pipeline from Kaggle datasets right now — once a Meta token (EAAG…) is added to .env.local, account analysis lights up with zero code changes.",
  },
  facebook: {
    what: "Paste-mode analysis works today; account-level analysis needs a Meta Graph API token.",
    demo: "34k Facebook comments are streaming through Kafka → Spark from the replay pool. Add a Meta token to .env.local and the account mode activates — the code is already built.",
  },
  threads: {
    what: "Full OAuth connect → analyze flow is built; it needs a Meta developer app with the Threads API use case.",
    demo: "THREADS_APP_ID/SECRET in .env.local + a registered redirect URI is all that's missing — connect, consent, and analyze your own threads exactly like YouTube/Reddit.",
  },
}

export default function PlatformAnalyze() {
  const { platform } = useParams()
  const navigate = useNavigate()
  const meta = PLATFORMS.find((p) => p.id === platform)

  if (!meta) {
    return <EmptyState text={`Unknown platform "${platform}" — pick one from the Analyze hub`} />
  }

  const name = meta.name
  const supportsAccount = ACCOUNT_SUPPORTED.has(platform)
  const isFuture = ["instagram", "facebook", "threads"].includes(platform)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ background: `${meta.color === "currentColor" ? "#a1a1aa" : meta.color}1f` }}
        >
          <meta.Logo size={20} />
        </span>
        <div>
          <h1 className="text-2xl font-extrabold">Analyze {name}</h1>
          <p className="text-xs" style={{ color: "var(--text-soft)" }}>
            {supportsAccount
              ? `Score a single ${name} post's comments, an entire account, or search by keyword`
              : `Score ${name} comments — keyword search, paste mode or single-post link`}
          </p>
        </div>
      </div>

      {isFuture && <FutureScopeHero platform={platform} name={name} meta={meta} />}

      {supportsAccount ? (
        <PlatformAnalyzeFull platform={platform} name={name} color={meta.color} navigate={navigate} />
      ) : (
        <PlatformAnalyzeLinkOnly platform={platform} name={name} navigate={navigate} />
      )}
    </div>
  )
}

function FutureScopeHero({ platform, name, meta }) {
  const note = FUTURE_NOTES[platform]
  const navigate = useNavigate()
  return (
    <Card className="border-dashed p-5">
      <div className="flex items-start gap-3">
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-base"
          style={{ background: `${meta.color === "currentColor" ? "#a1a1aa" : meta.color}1f` }}
        >
          🔭
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold">{name} · future scope</span>
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              style={{ background: "color-mix(in srgb, #3b82f6 15%, transparent)", color: "#60a5fa" }}
            >
              code built · creds pending
            </span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
            <strong>What works today:</strong> {note?.what}
          </p>
          <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
            <strong>Demo line:</strong> {note?.demo}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn text-xs" onClick={() => navigate("/sources")}>
              📊 See {name} data flowing now
            </button>
            <button className="btn text-xs" onClick={() => navigate("/analyze/youtube")}>
              🟢 Try the same flow on YouTube
            </button>
          </div>
        </div>
      </div>
    </Card>
  )
}

function PlatformAnalyzeFull({ platform, name, color, navigate }) {
  const [tab, setTab] = useState("post") // post | account | keyword
  const keywordSupported = KEYWORD_SUPPORTED.has(platform)
  return (
    <>
      <div className="flex gap-1.5">
        <button className={`chip ${tab === "post" ? "chip-active" : ""}`} onClick={() => setTab("post")}>
          🔗 Single post
        </button>
        <button className={`chip ${tab === "account" ? "chip-active" : ""}`} onClick={() => setTab("account")}>
          👤 Entire account
        </button>
        {keywordSupported && (
          <button className={`chip ${tab === "keyword" ? "chip-active" : ""}`} onClick={() => setTab("keyword")}>
            🔍 Keyword
          </button>
        )}
      </div>
      {tab === "post" ? (
        <PostForm platform={platform} name={name} navigate={navigate} />
      ) : tab === "keyword" ? (
        <KeywordForm platform={platform} navigate={navigate} />
      ) : platform === "threads" ? (
        <ThreadsAccountPanel name={name} navigate={navigate} />
      ) : (
        <AccountForm platform={platform} name={name} color={color} navigate={navigate} />
      )}
    </>
  )
}

function PlatformAnalyzeLinkOnly({ platform, name, navigate }) {
  return (
    <>
      {platform === "x" ? (
        <>
          <KeywordForm platform={platform} navigate={navigate} />
          <PostForm platform={platform} name={name} navigate={navigate} />
        </>
      ) : (
        <PasteForm />
      )}
      {platform !== "x" && (
        <Card className="p-4">
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
            <strong>{name} has no free public comment API.</strong> Paste comments manually (one per line),
            or set up a Meta Graph API token (<code>EAAG…</code> in <code>.env.local</code>) to unlock
            account-level analysis later.
          </p>
        </Card>
      )}
    </>
  )
}

function PasteForm() {
  const [text, setText] = useState("")
  const [title, setTitle] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean)
    if (!lines.length || loading) return
    setLoading(true); setError(null)
    try {
      const res = await analyzePost({ url: lines.join("\n"), mode: "paste", limit: lines.length, title: title.trim() || "Pasted comments" })
      if (res.status === "error") setError(res.message)
      else setText("")
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>
          Paste comments — one per line
        </label>
        <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>
          {text.split("\n").filter((l) => l.trim()).length} comments
        </span>
      </div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (optional) — e.g. Instagram post about the launch"
        className="input mb-2 w-full"
      />
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"Love this so much!\nThe update is disappointing…\nWhere can I buy this?"}
        rows={6}
        className="input w-full resize-y"
      />
      <div className="mt-3 flex items-center gap-3">
        <button className="btn btn-primary" onClick={submit} disabled={loading || !text.trim()}>
          {loading ? "Streaming to Kafka…" : "🚀 Analyze pasted comments"}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          scores appear in ~30–60s · watch them on the Live Feed
        </span>
      </div>
    </Card>
  )
}

function KeywordForm({ platform, navigate }) {
  const [keyword, setKeyword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [limit, setLimit] = useState(100)

  const submit = async () => {
    if (!keyword.trim() || loading) return
    setLoading(true); setError(null)
    try {
      const res = await keywordSearch({ platform, keyword: keyword.trim(), limit })
      if (res.status === "error") setError(res.message)
      else navigate(`/topics/${platform}/${encodeURIComponent(keyword.trim())}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const hint = {
    youtube: "Real YouTube search — fresh videos + their comments, live-scored",
    x: "Topic-matched X comments from the replay pool (X API is paid) — re-scored fresh",
    reddit: "Topic-matched Reddit comments from the replay pool (API bot-walled) — re-scored fresh",
  }[platform]

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>
          Search {platform === "x" ? "X" : platform} comments by keyword
        </label>
        <select className="select w-[130px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          <option value={50}>50 comments</option>
          <option value={100}>100 comments</option>
          <option value={200}>200 comments</option>
        </select>
      </div>
      <div className="flex gap-2">
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="e.g. wardrobe, trailer, update, price…"
          className="input flex-1"
        />
        <button className="btn btn-primary shrink-0" onClick={submit} disabled={loading || !keyword.trim()}>
          {loading ? "Fetching & streaming…" : "🔍 Analyze"}
        </button>
      </div>
      <div className="mt-2 flex items-center gap-3">
        {error && <span className="text-xs text-red-400">{error}</span>}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>{hint}</span>
      </div>
    </Card>
  )
}

function PostForm({ platform, name, navigate }) {
  const [url, setUrl] = useState("")
  const [pasteMode, setPasteMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [limit, setLimit] = useState(100)

  const submit = async () => {
    if (loading) return
    const value = url.trim()
    if (!pasteMode && !value) return
    if (pasteMode && !value) return
    setLoading(true); setError(null)
    try {
      const res = await analyzePost({ url: value, mode: pasteMode ? "paste" : "auto", limit })
      if (res.status === "error") setError(res.message)
      else navigate(`/analyze/post/${res.post_id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex gap-1.5">
          <button className={`chip ${!pasteMode ? "chip-active" : ""}`} onClick={() => setPasteMode(false)}>🔗 URL</button>
          <button className={`chip ${pasteMode ? "chip-active" : ""}`} onClick={() => setPasteMode(true)}>📝 Paste</button>
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
        placeholder={pasteMode ? "Paste comments — one per line…" : PLACEHOLDERS[platform]}
        rows={pasteMode ? 6 : 2}
        className="input w-full resize-y"
      />
      <div className="mt-3 flex items-center gap-3">
        <button className="btn btn-primary" onClick={submit} disabled={loading || !url.trim()}>
          {loading ? "Fetching & streaming…" : "🚀 Analyze"}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          scores appear in ~30–60s
        </span>
      </div>
    </Card>
  )
}

function AccountForm({ platform, name, color, navigate }) {
  const [handle, setHandle] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [maxPosts, setMaxPosts] = useState(5)
  const [limit, setLimit] = useState(100)

  const submit = async () => {
    if (!handle.trim() || loading) return
    setLoading(true); setError(null)
    try {
      const res = await analyzeAccount({
        platform,
        handle: handle.trim(),
        limit,
        max_videos: maxPosts,
      })
      if (res.status === "error") setError(res.message)
      else navigate(`/analyze/account/${platform}/${encodeURIComponent(res.handle)}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>
          {platform === "youtube" ? "YouTube channel handle" : "Reddit username"}
        </label>
        <div className="flex gap-2">
          <select className="select w-[120px]" value={maxPosts} onChange={(e) => setMaxPosts(Number(e.target.value))} title="how many posts to pull">
            {[3, 5, 8, 10].map((n) => (
              <option key={n} value={n}>{n} latest posts</option>
            ))}
          </select>
          <select className="select w-[130px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            <option value={50}>50 comments</option>
            <option value={100}>100 comments</option>
            <option value={200}>200 comments</option>
          </select>
        </div>
      </div>
      <input
        value={handle}
        onChange={(e) => setHandle(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder={platform === "youtube" ? "@MrBeast  or  https://youtube.com/@MrBeast" : "u/spez  or  spez"}
        className="input w-full"
      />
      <div className="mt-3 flex items-center gap-3">
        <button className="btn btn-primary" onClick={submit} disabled={loading || !handle.trim()}>
          {loading ? `Fetching ${name} account…` : `🚀 Analyze entire account`}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          every comment of each post → Kafka → Spark
        </span>
      </div>
    </Card>
  )
}

function ThreadsAccountPanel({ name, navigate }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [maxPosts, setMaxPosts] = useState(5)
  const [limit, setLimit] = useState(50)

  const loadStatus = () => fetchThreadsStatus().then(setStatus).catch(() => setStatus({ connected: false }))
  useEffect(() => { loadStatus() }, [])

  const connect = async () => {
    setError(null)
    try {
      const res = await threadsAuthUrl()
      if (res.status === "error") setError(res.message)
      else window.location.href = res.url
    } catch (e) {
      setError(e.message)
    }
  }

  const analyze = async () => {
    setLoading(true); setError(null)
    try {
      const handle = status?.username || ""
      const res = await analyzeAccount({ platform: "threads", handle, limit, max_videos: maxPosts })
      if (res.status === "error") setError(res.message)
      else navigate(`/analyze/account/threads/${encodeURIComponent(res.handle)}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const connected = status?.connected
  const configured = status?.configured

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>
          Connected Threads account
        </label>
        <div className="flex gap-2">
          <select className="select w-[120px]" value={maxPosts} onChange={(e) => setMaxPosts(Number(e.target.value))} disabled={!configured}>
            {[3, 5, 8, 10].map((n) => (
              <option key={n} value={n}>{n} latest threads</option>
            ))}
          </select>
          <select className="select w-[130px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))} disabled={!configured}>
            <option value={25}>25 replies</option>
            <option value={50}>50 replies</option>
            <option value={100}>100 replies</option>
          </select>
        </div>
      </div>

      {status == null ? (
        <p className="text-xs" style={{ color: "var(--text-faint)" }}>Checking connection…</p>
      ) : connected ? (
        <div className="flex items-center gap-2 rounded-lg border p-3" style={{ borderColor: "var(--border-soft)" }}>
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--positive)" }} />
          <span className="text-sm font-semibold">@{status.username}</span>
          <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>connected</span>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-lg border p-3" style={{ borderColor: "var(--border-soft)" }}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: configured ? "#eab308" : "#3b82f6" }} />
            <span className="text-sm" style={{ color: "var(--text-soft)" }}>
              {status.reason || "Not connected"}
            </span>
          </div>
          {configured ? (
            <button className="btn btn-primary" onClick={connect}>🔗 Connect Threads account</button>
          ) : (
            <div className="rounded-lg border border-dashed p-3" style={{ borderColor: "var(--border-soft)" }}>
              <p className="text-xs font-semibold">🔭 Future scope</p>
              <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--text-soft)" }}>
                Live Threads monitoring needs a Meta developer app with the <strong>"Threads API"</strong> use
                case, <code>THREADS_APP_ID</code>/<code>THREADS_APP_SECRET</code> in <code>.env.local</code>, and a
                registered OAuth redirect URI. The full connect → analyze flow is already built — add the
                credentials to light it up.
              </p>
            </div>
          )}
          {!configured && (
            <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-faint)" }}>
              The Threads API only reads <strong>your own connected profile</strong> — OAuth consent on connect.
            </p>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center gap-3">
        <button className="btn btn-primary" onClick={analyze} disabled={!connected || loading}>
          {loading ? "Fetching threads…" : "🚀 Analyze my threads"}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
        <span className="ml-auto text-[10px]" style={{ color: "var(--text-faint)" }}>
          every reply of each thread → Kafka → Spark
        </span>
      </div>
    </Card>
  )
}

import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { SentioWordmark } from "../components/Brand"

const BASE = import.meta.env.BASE_URL || ""

export default function ThreadsCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [state, setState] = useState({ loading: true, error: null, note: null })

  useEffect(() => {
    const code = params.get("code")
    const error = params.get("error")
    if (error) {
      setState({ loading: false, error: `OAuth denied: ${error}`, note: null })
      return
    }
    if (!code) {
      setState({ loading: false, error: "No authorization code in callback URL", note: null })
      return
    }
    fetch(`${BASE}/api/threads/callback?code=${encodeURIComponent(code)}`)
      .then((r) => r.json())
      .then((res) => {
        if (res.status === "error") setState({ loading: false, error: res.message, note: null })
        else setState({ loading: false, error: null, note: res.note })
      })
      .catch((e) => setState({ loading: false, error: e.message, note: null }))
  }, [])

  return (
    <div className="flex min-h-screen items-center justify-center" style={{ background: "var(--bg)" }}>
      <div className="card w-full max-w-md p-8 text-center">
        <div className="flex justify-center"><SentioWordmark size={38} sub={null} /></div>
        <h1 className="mt-5 text-lg font-extrabold">Threads OAuth</h1>
        {state.loading && (
          <p className="mt-2 text-sm" style={{ color: "var(--text-soft)" }}>Exchanging authorization code…</p>
        )}
        {!state.loading && !state.error && (
          <div className="mt-3 space-y-3">
            <p className="text-sm font-semibold text-emerald-400">✓ Connected</p>
            <p className="text-xs" style={{ color: "var(--text-soft)" }}>{state.note}</p>
            <button className="btn btn-primary w-full" onClick={() => navigate("/analyze/threads")}>
              Analyze my threads →
            </button>
          </div>
        )}
        {!state.loading && state.error && (
          <div className="mt-3 space-y-3">
            <p className="text-sm text-red-400">{state.error}</p>
            <button className="btn w-full" onClick={() => navigate("/analyze/threads")}>
              ← Back to Threads setup
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

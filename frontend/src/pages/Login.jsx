import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { loginRequest } from "../lib/api"
import { useAuth } from "../lib/auth"
import { SentioLogo, SentioWordmark, PLATFORMS } from "../components/Brand"

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e?.preventDefault()
    if (!email.trim() || !password || loading) return
    setLoading(true); setError(null)
    try {
      const res = await loginRequest({ email, password })
      if (res.status === "ok") {
        login(res.user)
        navigate("/dashboard")
      } else setError(res.message || "Login failed")
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* brand panel */}
      <div className="login-gradient relative hidden flex-col justify-between p-12 lg:flex">
        <SentioWordmark size={44} sub="SOCIAL PULSE ANALYTICS" />
        <div>
          <h1 className="max-w-md text-4xl font-extrabold leading-tight text-white">
            Feel the <span className="grad-text">pulse</span> of social media, live.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-white/60">
            Stream comments from Reddit, YouTube, Instagram, Facebook and X through a real-time
            Kafka + Spark pipeline. Scored by VADER and DistilBERT — compared, evaluated, visualized.
          </p>
          <div className="mt-8 flex items-center gap-6">
            {PLATFORMS.map((p) => (
              <span key={p.id} title={p.name} className="opacity-90">{<p.Logo size={26} />}</span>
            ))}
          </div>
        </div>
        <div className="text-[11px] text-white/40">
          Kafka · Spark Structured Streaming · PostgreSQL · FastAPI · React
        </div>
      </div>

      {/* form panel */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex justify-center lg:hidden"><SentioLogo size={52} /></div>
          <h2 className="text-2xl font-bold">Welcome to Sentio</h2>
          <p className="mt-1.5 text-sm" style={{ color: "var(--text-soft)" }}>
            Sign in to your analytics workspace
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input mt-1.5 w-full"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="any password works"
                className="input mt-1.5 w-full"
              />
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button type="submit" disabled={loading || !email || !password} className="btn-primary btn w-full justify-center !py-3">
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-5 text-center text-[11px]" style={{ color: "var(--text-faint)" }}>
            Demo workspace — any email + password signs you in
          </p>
        </div>
      </div>
    </div>
  )
}

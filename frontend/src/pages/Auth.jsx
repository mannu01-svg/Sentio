import { useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { loginRequest, signupRequest } from "../lib/api"
import { useAuth } from "../lib/auth"
import { SentioLogo } from "../components/Brand"

function useAuthForm() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null)
  return { name, setName, email, setEmail, password, setPassword, confirm, setConfirm, loading, setLoading, error, setError, pending, setPending }
}

export function AuthCard({ mode = "login" }) {
  const signup = mode === "signup"
  const f = useAuthForm()
  const { login } = useAuth()
  const navigate = useNavigate()

  const submit = async (e) => {
    e?.preventDefault()
    if (f.loading) return
    if (signup) {
      if (!f.name.trim() || !f.email.trim() || !f.password) return
      if (f.password !== f.confirm) { f.setError("Passwords don't match"); return }
    } else if (!f.email.trim() || !f.password) return
    f.setLoading(true); f.setError(null)
    try {
      const res = signup
        ? await signupRequest({ name: f.name, email: f.email, password: f.password })
        : await loginRequest({ email: f.email, password: f.password })
      if (res.status === "ok") {
        login(res.user, res.token)
        navigate("/dashboard")
      } else if (res.status === "pending") {
        f.setPending(res.message || "Account awaiting admin approval")
      } else {
        f.setError(res.message || "Something went wrong")
      }
    } catch (err) {
      f.setError(err.message)
    } finally {
      f.setLoading(false)
    }
  }

  if (f.pending) {
    return (
      <div className="auth-card">
        <div className="flex justify-center"><SentioLogo size={44} /></div>
        <h1 className="mt-5 text-center text-xl font-semibold tracking-tight">Request received</h1>
        <p className="mt-3 text-center text-sm" style={{ color: "var(--text-soft)" }}>{f.pending}</p>
        <div className="mt-6 flex justify-center">
          <button className="btn-primary btn justify-center !py-2.5" onClick={() => { f.setPending(null); f.setEmail(""); f.setPassword(""); f.setConfirm("") }}>
            Back to sign in
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-card">
      <div className="flex justify-center"><SentioLogo size={44} /></div>
      <h1 className="mt-5 text-center text-xl font-semibold tracking-tight">
        {signup ? "Create your account" : "Welcome back"}
      </h1>
      <p className="mt-1.5 text-center text-sm" style={{ color: "var(--text-soft)" }}>
        {signup ? "Sign up — an admin approves new accounts" : "Sign in to your Sentio workspace"}
      </p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        {signup && (
          <div>
            <label className="auth-label">Name</label>
            <input type="text" value={f.name} onChange={(e) => f.setName(e.target.value)}
              placeholder="Ada Lovelace" className="input mt-1.5 w-full" autoFocus />
          </div>
        )}
        <div>
          <label className="auth-label">Email</label>
          <input type="email" value={f.email} onChange={(e) => f.setEmail(e.target.value)}
            placeholder="you@example.com" className="input mt-1.5 w-full" autoFocus={!signup} />
        </div>
        <div>
          <label className="auth-label">Password</label>
          <input type="password" value={f.password} onChange={(e) => f.setPassword(e.target.value)}
            placeholder={signup ? "At least 6 characters" : "Your password"} className="input mt-1.5 w-full" />
        </div>
        {signup && (
          <div>
            <label className="auth-label">Confirm password</label>
            <input type="password" value={f.confirm} onChange={(e) => f.setConfirm(e.target.value)}
              placeholder="Repeat your password" className="input mt-1.5 w-full" />
          </div>
        )}

        {f.error && <p className="auth-error">{f.error}</p>}

        <button type="submit"
          disabled={f.loading || !f.email || !f.password || (signup && (!f.name || !f.confirm))}
          className="btn-primary btn w-full justify-center !py-2.5">
          {f.loading ? (signup ? "Creating account…" : "Signing in…") : (signup ? "Create account" : "Sign in")}
        </button>
      </form>

      <p className="mt-6 text-center text-[13px]" style={{ color: "var(--text-soft)" }}>
        {signup ? "Already have an account?" : "New to Sentio?"}{" "}
        <Link to={signup ? "/login" : "/signup"} className="auth-link">
          {signup ? "Sign in" : "Create one"}
        </Link>
      </p>
    </div>
  )
}

export default function Auth({ mode: initialMode = null }) {
  const mode = initialMode || (window.location.pathname.includes("signup") ? "signup" : "login")
  const { user } = useAuth()
  if (user) return <Navigate to="/dashboard" replace />
  return (
    <div className="auth-page">
      <AuthCard mode={mode} />
    </div>
  )
}

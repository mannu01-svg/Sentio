import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../lib/auth"
import { useTheme } from "../lib/hooks"
import { Card, SectionTitle } from "../components/UI"
import { SentioLogo } from "../components/Brand"
import {
  adminApproveUser,
  adminDeleteUser,
  adminListUsers,
  adminRejectUser,
  adminSetRole,
} from "../lib/api"

function UserManagement() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminListUsers()
      setUsers(res.users || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const act = async (email, fn, label) => {
    setBusy(email + label)
    setError(null)
    try {
      await fn(email)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  const statusChip = (status) => {
    const map = {
      approved: "chip-active",
      pending: "",
      rejected: "",
    }
    return `chip ${map[status] || ""}`
  }

  return (
    <Card className="p-5 xl:col-span-2">
      <SectionTitle title="User management" detail="Approve signups, toggle admins, remove accounts" />
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[10px]" style={{ color: "var(--text-faint)" }}>
          New signups start as <b>pending</b> — approve them before they can sign in.
        </p>
        <button className="btn text-xs" onClick={load} disabled={loading}>↻ Refresh</button>
      </div>
      {error && <p className="auth-error mb-3">{error}</p>}
      {loading ? (
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>Loading accounts…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr style={{ color: "var(--text-faint)" }}>
                <th className="px-2 py-2">User</th>
                <th className="px-2 py-2">Role</th>
                <th className="px-2 py-2">Status</th>
                <th className="px-2 py-2">Last login</th>
                <th className="px-2 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.email} className="border-t" style={{ borderColor: "var(--border-soft)" }}>
                  <td className="px-2 py-2.5">
                    <div className="font-bold">{u.name}</div>
                    <div style={{ color: "var(--text-soft)" }}>{u.email}</div>
                  </td>
                  <td className="px-2 py-2.5">
                    <span className="chip">{u.role === "admin" ? "★ admin" : "user"}</span>
                  </td>
                  <td className="px-2 py-2.5">
                    <span className={statusChip(u.status)}>{u.status}</span>
                  </td>
                  <td className="px-2 py-2.5" style={{ color: "var(--text-soft)" }}>
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                  </td>
                  <td className="px-2 py-2.5">
                    <div className="flex flex-wrap justify-end gap-1.5">
                      {u.status === "pending" && (
                        <>
                          <button
                            className="chip chip-active"
                            disabled={busy === u.email + "approve"}
                            onClick={() => act(u.email, adminApproveUser, "approve")}
                          >
                            ✓ Approve
                          </button>
                          <button
                            className="chip"
                            disabled={busy === u.email + "reject"}
                            onClick={() => act(u.email, adminRejectUser, "reject")}
                          >
                            ✕ Reject
                          </button>
                        </>
                      )}
                      {u.status === "rejected" && (
                        <button
                          className="chip chip-active"
                          disabled={busy === u.email + "approve"}
                          onClick={() => act(u.email, adminApproveUser, "approve")}
                        >
                          ✓ Re-approve
                        </button>
                      )}
                      <button
                        className="chip"
                        disabled={busy === u.email + "role"}
                        onClick={() => act(u.email, (e) => adminSetRole(e, u.role === "admin" ? "user" : "admin"), "role")}
                      >
                        {u.role === "admin" ? "Demote" : "Make admin"}
                      </button>
                      <button
                        className="chip"
                        disabled={busy === u.email + "delete"}
                        onClick={() => { if (window.confirm(`Delete ${u.email}? This cannot be undone.`)) act(u.email, adminDeleteUser, "delete") }}
                      >
                        🗑 Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr><td colSpan={5} className="px-2 py-4 text-center" style={{ color: "var(--text-soft)" }}>No accounts yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export default function Settings() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const [pollMs, setPollMs] = useState(() => Number(localStorage.getItem("sentio-poll") || 3000))

  const savePoll = (ms) => {
    setPollMs(ms)
    localStorage.setItem("sentio-poll", ms)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Settings</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>Workspace preferences</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-5">
          <SectionTitle title="Profile" detail="Your workspace identity" />
          <div className="flex items-center gap-4">
            <span
              className="flex size-14 items-center justify-center rounded-2xl text-xl font-bold text-white"
              style={{ background: "linear-gradient(135deg, var(--accent), var(--accent3))" }}
            >
              {(user?.name || "U")[0].toUpperCase()}
            </span>
            <div>
              <div className="text-sm font-bold">{user?.name}</div>
              <div className="text-xs" style={{ color: "var(--text-soft)" }}>{user?.email}</div>
            </div>
          </div>
          <button
            className="btn mt-5"
            onClick={() => { logout(); navigate("/login") }}
          >
            ⎋ Sign out
          </button>
        </Card>

        <Card className="p-5">
          <SectionTitle title="Appearance" detail="Light or dark — your call" />
          <div className="flex items-center justify-between rounded-xl border px-4 py-3" style={{ borderColor: "var(--border-soft)" }}>
            <div className="flex items-center gap-3">
              <SentioLogo size={26} />
              <div>
                <div className="text-xs font-bold">{theme === "dark" ? "Dark theme" : "Light theme"}</div>
                <div className="text-[10px]" style={{ color: "var(--text-faint)" }}>Applies instantly across the app</div>
              </div>
            </div>
            <button
              onClick={toggle}
              className="relative h-7 w-14 rounded-full transition"
              style={{ background: theme === "dark" ? "linear-gradient(90deg, var(--accent), var(--accent2))" : "var(--border)" }}
              aria-label="Toggle theme"
            >
              <span
                className="absolute top-1 size-5 rounded-full bg-white shadow transition-all"
                style={{ left: theme === "dark" ? 32 : 4 }}
              />
            </button>
          </div>

          <SectionTitle title="Live polling speed" detail="How often the dashboard refreshes" />
          <div className="flex gap-2">
            {[2000, 3000, 5000, 10000].map((ms) => (
              <button
                key={ms}
                className={`chip ${pollMs === ms ? "chip-active" : ""}`}
                onClick={() => savePoll(ms)}
              >
                {ms / 1000}s
              </button>
            ))}
          </div>
          <p className="mt-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
            Note: polling speed applies to pages using the shared polling hook (default 3s per page).
          </p>
        </Card>

        <Card className="p-5 xl:col-span-2">
          <SectionTitle title="About Sentio" detail="Social pulse analytics — college project" />
          <div className="grid gap-3 text-xs sm:grid-cols-3">
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
              <div className="font-bold" style={{ color: "var(--accent)" }}>Pipeline</div>
              <p className="mt-1 leading-relaxed" style={{ color: "var(--text-soft)" }}>
                Kafka → Spark Structured Streaming → PostgreSQL → FastAPI
              </p>
            </div>
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
              <div className="font-bold" style={{ color: "var(--accent2)" }}>Models</div>
              <p className="mt-1 leading-relaxed" style={{ color: "var(--text-soft)" }}>
                VADER (lexicon) + DistilBERT-SST2 (transformer), compared & evaluated
              </p>
            </div>
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
              <div className="font-bold" style={{ color: "var(--accent3)" }}>Sources</div>
              <p className="mt-1 leading-relaxed" style={{ color: "var(--text-soft)" }}>
                Reddit · YouTube · Instagram · Facebook · X — Kaggle datasets + live link fetches
              </p>
            </div>
          </div>
        </Card>

        {user?.role === "admin" && <UserManagement />}
      </div>
    </div>
  )
}

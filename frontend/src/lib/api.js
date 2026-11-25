const BASE = ""

// the logged-in user's session token (set by AuthProvider in localStorage) —
// sent as Authorization: Bearer on every mutating/account-scoped call
export function currentToken() {
  try {
    return localStorage.getItem("sentio-token") || null
  } catch {
    return null
  }
}

// the logged-in user (set by AuthProvider in localStorage) — attached to every
// analyze call so history is attributed to the account that ran it
export function currentUserEmail() {
  try {
    const raw = localStorage.getItem("sentio-user")
    return raw ? (JSON.parse(raw)?.email ?? null) : null
  } catch {
    return null
  }
}

function authHeaders() {
  const token = currentToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  if (res.status === 401) handleAuthExpired()
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (res.status === 401) handleAuthExpired()
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

// a 401 means the stored session is dead (API restart/expiry) — drop it and
// send the user to sign-in instead of hammering every call with a stale token
function handleAuthExpired() {
  try {
    localStorage.removeItem("sentio-token")
    localStorage.removeItem("sentio-user")
  } catch {
    /* localStorage unavailable — nothing to clear */
  }
  if (!window.location.pathname.startsWith("/login")) {
    window.location.replace("/login")
  }
}

// ---- data endpoints ----
export const fetchSummary = () => get("/api/summary")
export const fetchTimeline = (minutes = 60) => get(`/api/timeline?minutes=${minutes}`)
export const fetchComments = ({ limit = 30, source, sentiment, q, post_id } = {}) => {
  const params = new URLSearchParams({ limit })
  if (source) params.set("source", source)
  if (sentiment) params.set("sentiment", sentiment)
  if (q) params.set("q", q)
  if (post_id) params.set("post_id", post_id)
  return get(`/api/comments?${params}`)
}
export const fetchWords = (limit = 12) => get(`/api/words?limit=${limit}`)
export const fetchCompare = (limit = 1000) => get(`/api/compare?limit=${limit}`)
export const fetchTrends = (limit = 10, source) => {
  const params = new URLSearchParams({ limit })
  if (source) params.set("source", source)
  return get(`/api/trends?${params}`)
}
export const fetchAlerts = () => get("/api/alerts")
export const fetchSpam = (limit = 2000) => get(`/api/spam?limit=${limit}`)
export const fetchPosts = ({ user } = {}) => {
  const params = new URLSearchParams()
  const userEmail = user ?? currentUserEmail()
  if (userEmail) params.set("user", userEmail)
  const qs = params.toString()
  return get(`/api/posts${qs ? `?${qs}` : ""}`)
}
export const fetchAccounts = ({ user } = {}) => {
  const params = new URLSearchParams()
  const userEmail = user ?? currentUserEmail()
  if (userEmail) params.set("user", userEmail)
  const qs = params.toString()
  return get(`/api/accounts${qs ? `?${qs}` : ""}`)
}
export const fetchHistory = ({ kind, platform, user, limit = 100 } = {}) => {
  const params = new URLSearchParams({ limit })
  const userEmail = user ?? currentUserEmail()
  if (kind) params.set("kind", kind)
  if (platform) params.set("platform", platform)
  if (userEmail) params.set("user", userEmail)
  return get(`/api/history?${params}`)
}
export const fetchPipeline = () => get("/api/pipeline")
export const fetchTrending = () => get("/api/trending")
export const fetchTopicStreams = ({ user } = {}) => {
  const params = new URLSearchParams()
  const userEmail = user ?? currentUserEmail()
  if (userEmail) params.set("user", userEmail)
  const qs = params.toString()
  return get(`/api/topics/streams${qs ? `?${qs}` : ""}`)
}
export const fetchStreamStatus = () => get("/api/stream/status")
export const startLiveStream = ({ minutes = 3, rate = 40 } = {}) =>
  post("/api/stream/live", { minutes, rate })
export const stopLiveStream = () => post("/api/stream/stop", {})
export const keywordSearch = ({ platform, keyword, limit = 100 }) =>
  post("/api/keyword-search", { platform, keyword, limit, user_email: currentUserEmail() })

// ---- actions ----
export const analyzePost = ({ url, mode = "auto", limit = 100, title }) =>
  post("/api/analyze", { url, mode, limit, title, user_email: currentUserEmail() })
export const analyzeAccount = ({ platform, handle, limit = 100, max_videos = 5 }) =>
  post("/api/analyze-account", { platform, handle, limit, max_videos, user_email: currentUserEmail() })
export const fetchThreadsStatus = () => get("/api/threads/status")
export const threadsAuthUrl = () => get("/api/threads/auth-url")
export const loginRequest = ({ email, password }) =>
  post("/api/login", { email, password })
export const signupRequest = ({ name, email, password }) =>
  post("/api/signup", { name, email, password })

// ---- admin: user management (Settings -> User Management, admin only) ----
export const adminListUsers = () => get("/api/admin/users")
export const adminApproveUser = (email) =>
  post("/api/admin/users/approve", { email })
export const adminRejectUser = (email) =>
  post("/api/admin/users/reject", { email })
export const adminSetRole = (email, role) =>
  post("/api/admin/users/role", { email, role })
export const adminDeleteUser = (email) =>
  post("/api/admin/users/delete", { email })

// ---- history re-score (lost comments -> re-fetch -> Kafka -> rescored) ----
export const rehydrateHistory = (entryId) =>
  post(`/api/history/${entryId}/rehydrate`, {})

export function exportUrl(filters = {}) {
  const params = new URLSearchParams()
  if (filters.source) params.set("source", filters.source)
  if (filters.sentiment) params.set("sentiment", filters.sentiment)
  if (filters.q) params.set("q", filters.q)
  if (filters.post_id) params.set("post_id", filters.post_id)
  return `${BASE}/api/export?${params}`
}

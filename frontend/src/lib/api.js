const BASE = ""

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
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
export const fetchTrends = (limit = 10) => get(`/api/trends?limit=${limit}`)
export const fetchAlerts = () => get("/api/alerts")
export const fetchSpam = (limit = 2000) => get(`/api/spam?limit=${limit}`)
export const fetchPosts = () => get("/api/posts")
export const fetchPipeline = () => get("/api/pipeline")

// ---- actions ----
export const analyzePost = ({ url, mode = "auto", limit = 100, title }) =>
  post("/api/analyze", { url, mode, limit, title })
export const loginRequest = ({ email, password, name }) =>
  post("/api/login", { email, password, name })

export function exportUrl(filters = {}) {
  const params = new URLSearchParams()
  if (filters.source) params.set("source", filters.source)
  if (filters.sentiment) params.set("sentiment", filters.sentiment)
  if (filters.q) params.set("q", filters.q)
  if (filters.post_id) params.set("post_id", filters.post_id)
  return `${BASE}/api/export?${params}`
}

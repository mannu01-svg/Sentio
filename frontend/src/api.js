const BASE = ""

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

export const fetchSummary = () => get("/api/summary")
export const fetchTimeline = (minutes = 60) => get(`/api/timeline?minutes=${minutes}`)
export const fetchComments = ({ limit = 30, source, sentiment, q } = {}) => {
  const params = new URLSearchParams({ limit })
  if (source) params.set("source", source)
  if (sentiment) params.set("sentiment", sentiment)
  if (q) params.set("q", q)
  return get(`/api/comments?${params}`)
}
export const fetchWords = (limit = 12) => get(`/api/words?limit=${limit}`)
export const fetchCompare = (limit = 1000) => get(`/api/compare?limit=${limit}`)

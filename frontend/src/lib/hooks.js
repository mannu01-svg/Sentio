import { useEffect, useState } from "react"

const KEY = "sentio-theme"

export function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem(KEY) || "dark")
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(KEY, theme)
  }, [theme])
  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"))
  return { theme, toggle }
}

export function usePolling(fn, deps = [], interval = 3000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [paused, setPaused] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  useEffect(() => {
    if (paused) return
    let alive = true
    const tick = () =>
      fn()
        .then((d) => {
          if (!alive) return
          setData(d)
          setError(null)
          setLastUpdated(new Date())
        })
        .catch((e) => alive && setError(e.message))
    tick()
    const id = setInterval(tick, interval)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, paused, interval])
  return { data, error, paused, setPaused, lastUpdated }
}

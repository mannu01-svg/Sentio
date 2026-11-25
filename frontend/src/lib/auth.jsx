import { createContext, useContext, useEffect, useState } from "react"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem("sentio-user")
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  const [token, setToken] = useState(() => localStorage.getItem("sentio-token"))

  useEffect(() => {
    if (user) localStorage.setItem("sentio-user", JSON.stringify(user))
    else localStorage.removeItem("sentio-user")
  }, [user])

  useEffect(() => {
    if (token) localStorage.setItem("sentio-token", token)
    else localStorage.removeItem("sentio-token")
  }, [token])

  const login = (u, t) => {
    setUser(u)
    if (t) setToken(t)
  }
  const logout = () => {
    setUser(null)
    setToken(null)
  }

  return <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

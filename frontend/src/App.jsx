import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { useEffect } from "react"
import { useAuth } from "./lib/auth"
import Auth from "./pages/Auth"
import Dashboard from "./pages/Dashboard"
import Live from "./pages/Live"
import Analyze from "./pages/Analyze"
import AnalyzeDetail from "./pages/AnalyzeDetail"
import Trends from "./pages/Trends"
import Models from "./pages/Models"
import Pipeline from "./pages/Pipeline"
import Sources from "./pages/Sources"
import Settings from "./pages/Settings"
import { NAV, AppShell } from "./components/UI"

function Protected({ children }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace />
  return <AppShell nav={NAV}><div className="page-enter" key={location.pathname}>{children}</div></AppShell>
}

export default function App() {
  const location = useLocation()
  useEffect(() => {
    document.title = "Sentio — Social Pulse Analytics"
  }, [])
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />
      <Route path="/signup" element={<Auth />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/live" element={<Protected><Live /></Protected>} />
      <Route path="/analyze" element={<Protected><Analyze /></Protected>} />
      <Route path="/analyze/:postId" element={<Protected><AnalyzeDetail /></Protected>} />
      <Route path="/trends" element={<Protected><Trends /></Protected>} />
      <Route path="/models" element={<Protected><Models /></Protected>} />
      <Route path="/pipeline" element={<Protected><Pipeline /></Protected>} />
      <Route path="/sources" element={<Protected><Sources /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

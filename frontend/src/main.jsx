import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import { AuthProvider } from './lib/auth.jsx'
import { useTheme } from './lib/hooks.js'
import App from './App.jsx'

function ThemeInit({ children }) {
  useTheme()
  return children
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ThemeInit>
          <App />
        </ThemeInit>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)

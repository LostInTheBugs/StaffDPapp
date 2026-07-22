import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import * as api from '../api/client'

interface User {
  id: number; email: string; first_name: string; last_name: string; full_name: string
  avatar_url: string | null
  delegue_status: string; delegue_role: string; role: string
  totp_enabled: boolean
  is_delegue_securite_sante: boolean; is_delegue_egalite: boolean
}

interface Organization {
  id: number; name: string; slug: string; company_name: string | null
  country: string; employee_count: number; mandate_end_date: string | null; required_titulaires: number
 weekly_credit_hours: number | null
}

interface AuthState { user: User | null; organization: Organization | null; token: string | null }

interface AuthContextType extends AuthState {
  setAuth: (token: string, user: User, org: Organization) => void
  logout: () => void; fetchDashboard: () => Promise<void>
  loading: boolean; error: string | null; setError: (msg: string | null) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const token = localStorage.getItem('token')
    return { user: null, organization: null, token }
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const setAuth = useCallback((token: string, user: User, org: Organization) => {
    localStorage.setItem('token', token)
    setState({ token, user, organization: org })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setState({ token: null, user: null, organization: null })
    navigate('/')
  }, [navigate])

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const dash = await api.getDashboard()
      setState({ token: localStorage.getItem('token'), user: dash.user, organization: dash.organization })
    } catch { logout() }
    finally { setLoading(false) }
  }, [logout])

  return (
    <AuthContext.Provider value={{ ...state, setAuth, logout, fetchDashboard, loading, error, setError }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}

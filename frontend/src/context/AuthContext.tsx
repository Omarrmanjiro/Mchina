import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { fetchMe, loginRequest, registerRequest, type RegisterBody } from '../api/client'

const TOKEN_KEY = 'mchina_token'
const EMAIL_KEY = 'mchina_email'

type AuthContextValue = {
  token: string | null
  email: string | null
  isPro: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterBody) => Promise<void>
  logout: () => void
  upgradeToProLocally: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  )
  const [email, setEmail] = useState<string | null>(() =>
    localStorage.getItem(EMAIL_KEY),
  )
  const [isPro, setIsPro] = useState(false)

  // Fetch me on mount if token exists
  useEffect(() => {
    if (token) {
      fetchMe(token).then(user => setIsPro(user.is_pro)).catch(() => {
        // optionally handle token expiration
      })
    } else {
      setIsPro(false)
    }
  }, [token])

  const login = useCallback(async (e: string, password: string) => {
    const data = await loginRequest(e, password)
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(EMAIL_KEY, e)
    setToken(data.access_token)
    setEmail(e)
    const user = await fetchMe(data.access_token)
    setIsPro(user.is_pro)
  }, [])

  const register = useCallback(async (payload: RegisterBody) => {
    await registerRequest(payload)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EMAIL_KEY)
    setToken(null)
    setEmail(null)
    setIsPro(false)
  }, [])

  const upgradeToProLocally = useCallback(() => {
    setIsPro(true)
  }, [])

  const value = useMemo(
    () => ({ token, email, isPro, login, register, logout, upgradeToProLocally }),
    [token, email, isPro, login, register, logout, upgradeToProLocally],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}

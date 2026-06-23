import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  fetchMe,
  loginRequest,
  logoutRequest,
  registerRequest,
  type RegisterBody,
} from '../api/client'

type AuthContextValue = {
  email: string | null
  isPro: boolean
  isAdmin: boolean
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterBody) => Promise<void>
  logout: () => Promise<void>
  upgradeToProLocally: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null)
  const [isPro, setIsPro] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // The JWT lives only in an httpOnly cookie set by the backend — it's never
  // stored in localStorage or read by JS. On mount, we ask the backend
  // "who am I?" via the cookie that the browser sends automatically. If
  // that fails (no cookie, expired, tampered), we're simply logged out.
  useEffect(() => {
    let cancelled = false

    fetchMe()
      .then((user) => {
        if (cancelled) return
        setEmail(user.email)
        setIsPro(user.is_pro)
        setIsAdmin(user.is_admin)
      })
      .catch(() => {
        if (cancelled) return
        setEmail(null)
        setIsPro(false)
        setIsAdmin(false)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (e: string, password: string) => {
    // loginRequest sets the httpOnly cookie server-side; nothing to store here.
    await loginRequest(e, password)
    const user = await fetchMe()
    setEmail(user.email)
    setIsPro(user.is_pro)
    setIsAdmin(user.is_admin)
  }, [])

  const register = useCallback(async (payload: RegisterBody) => {
    await registerRequest(payload)
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      setEmail(null)
      setIsPro(false)
      setIsAdmin(false)
    }
  }, [])

  const upgradeToProLocally = useCallback(() => {
    setIsPro(true)
  }, [])

  const value = useMemo(
    () => ({
      email,
      isPro,
      isAdmin,
      isLoading,
      isAuthenticated: email !== null,
      login,
      register,
      logout,
      upgradeToProLocally,
    }),
    [email, isPro, isAdmin, isLoading, login, register, logout, upgradeToProLocally],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
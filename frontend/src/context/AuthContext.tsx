import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactElement, ReactNode } from 'react'

import type { LoginSuccess } from '../api/auth'
import type { InitialSetupPayload, UserProfile } from '../api/types'
import {
  completeInitialSetup as performInitialSetup,
  fetchInitialSetupStatus,
  fetchProfile,
  login as performLogin,
  logout as performLogout,
  resolveCsrfToken,
} from '../api/auth'

type ApiError = Error & { status?: number }

interface AuthContextValue {
  user: UserProfile | null
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<UserProfile>
  logout: () => Promise<void>
  refreshSession: () => Promise<void>
  completeInitialSetup: (payload: InitialSetupPayload) => Promise<UserProfile>
  checkInitialSetupStatus: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps): ReactElement {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const bootstrap = useCallback(async () => {
    setLoading(true)
    try {
      const profile = await fetchProfile()
      setUser(profile)
      setCsrfToken(resolveCsrfToken())
      setError(null)
    } catch (caught) {
      const problem = caught as ApiError
      setUser(null)
      setCsrfToken(null)
      if (typeof problem.status === 'number' && problem.status === 401) {
        setError(null)
      } else {
        const message = problem?.message?.trim() || 'Unable to confirm your session. Please try again.'
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  const applySession = useCallback(
    (result: LoginSuccess) => {
      setUser(result.session.user)
      setCsrfToken(result.csrfToken ?? resolveCsrfToken())
      setLoading(false)
      setError(null)
    },
    [resolveCsrfToken],
  )

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    const result = await performLogin({ email, password })
    applySession(result)
    return result.session.user
  }, [applySession])

  const completeInitialSetup = useCallback(
    async (payload: InitialSetupPayload) => {
      setError(null)
      const result = await performInitialSetup(payload)
      applySession(result)
      return result.session.user
    },
    [applySession],
  )

  const logout = useCallback(async () => {
    const token = csrfToken ?? resolveCsrfToken()
    await performLogout(token)
    setUser(null)
    setCsrfToken(null)
    setError(null)
  }, [csrfToken])

  const refreshSession = useCallback(async () => {
    await bootstrap()
  }, [bootstrap])

  const checkInitialSetupStatus = useCallback(async () => {
    const status = await fetchInitialSetupStatus()
    return Boolean(status.initialSetupRequired)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      error,
      login,
      logout,
      refreshSession,
      completeInitialSetup,
      checkInitialSetupStatus,
    }),
    [
      user,
      loading,
      error,
      login,
      logout,
      refreshSession,
      completeInitialSetup,
      checkInitialSetupStatus,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

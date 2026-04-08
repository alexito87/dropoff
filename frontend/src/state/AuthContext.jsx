import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('dropoff_access_token'))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(token))

  useEffect(() => {
    async function bootstrap() {
      if (!token) {
        setLoading(false)
        setUser(null)
        return
      }

      try {
        const profile = await apiGet('/api/v1/users/me', true)
        setUser(profile)
      } catch {
        localStorage.removeItem('dropoff_access_token')
        setToken(null)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    bootstrap()
  }, [token])

  async function login(email, password) {
    const data = await apiPost('/api/v1/auth/login', { email, password })
    localStorage.setItem('dropoff_access_token', data.access_token)
    setToken(data.access_token)
    const profile = await apiGet('/api/v1/users/me', true)
    setUser(profile)
    return profile
  }

  function logout() {
    localStorage.removeItem('dropoff_access_token')
    setToken(null)
    setUser(null)
  }

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      isAuthenticated: Boolean(token),
      login,
      logout,
      setUser,
    }),
    [token, user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return context
}
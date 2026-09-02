import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import api from '../services/api'
import type { User } from '../types'

interface AuthContextType {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (data: { email: string; password: string; password_confirm: string; first_name: string; last_name: string }) => Promise<void>
  verifyEmail: (email: string, otp: string) => Promise<void>
  updateProfile: (data: Partial<User>) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const storedToken = localStorage.getItem('pam_token')
    const storedUser = localStorage.getItem('pam_user')
    if (storedToken && storedUser) {
      setToken(storedToken)
      try {
        setUser(JSON.parse(storedUser))
      } catch {
        localStorage.removeItem('pam_token')
        localStorage.removeItem('pam_user')
      }
    }
    setLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/auth/login/', { email, password })
    setToken(data.token)
    setUser(data.user)
    localStorage.setItem('pam_token', data.token)
    localStorage.setItem('pam_user', JSON.stringify(data.user))
  }

  const logout = async () => {
    try { await api.post('/auth/logout/') } catch { /* ignore */ }
    setToken(null)
    setUser(null)
    localStorage.removeItem('pam_token')
    localStorage.removeItem('pam_user')
  }

  const register = async (data: { email: string; password: string; password_confirm: string; first_name: string; last_name: string }) => {
    await api.post('/auth/register/', data)
  }

  const verifyEmail = async (email: string, otp: string) => {
    await api.post('/auth/verify-email/', { email, otp })
  }

  const updateProfile = async (data: Partial<User>) => {
    const res = await api.patch('/auth/profile/', data)
    const updatedUser = { ...user, ...res.data }
    setUser(updatedUser)
    localStorage.setItem('pam_user', JSON.stringify(updatedUser))
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, register, verifyEmail, updateProfile }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

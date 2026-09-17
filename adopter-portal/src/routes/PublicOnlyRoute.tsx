import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ReactNode } from 'react'

export default function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { user, token, loading } = useAuth()
  if (loading) return null
  if (token && user) return <Navigate to="/applications" replace />
  return <>{children}</>
}

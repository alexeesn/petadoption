import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { user, token, loading } = useAuth()
  if (loading) return null
  if (!token || !user) return <Navigate to="/login" replace />
  if (!user.is_email_verified) return <Navigate to="/verify-email" replace />
  return <Outlet />
}

import { useState, FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { Alert, FieldError } from '../components/UI'

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  const [email, setEmail] = useState(initialEmail)
  const [otp, setOtp] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/reset-password/', {
        email, otp, new_password: newPassword, new_password_confirm: confirmPassword,
      })
      setSuccess('Password reset successfully! You can now log in.')
      setTimeout(() => navigate('/login'), 1500)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { error?: string; new_password_confirm?: string[] } } }
      setError(anyErr?.response?.data?.error || anyErr?.response?.data?.new_password_confirm?.[0] || 'Reset failed. Please check your code.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="auth-card">
        <h1 className="text-3xl font-extrabold text-primary-900 text-center">Reset password</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Enter the reset code and your new password.
        </p>

        {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
        {success && <div className="mt-4"><Alert type="success">{success}</Alert></div>}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="field-label">Email</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="field-input mt-1" />
          </div>
          <div>
            <label htmlFor="otp" className="field-label">Reset code</label>
            <input id="otp" type="text" inputMode="numeric" maxLength={6} required value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} placeholder="123456"
              className="field-input mt-1 tracking-widest" />
          </div>
          <div>
            <label htmlFor="new_password" className="field-label">New password</label>
            <input id="new_password" type="password" required value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="field-input mt-1" />
          </div>
          <div>
            <label htmlFor="confirm_password" className="field-label">Confirm new password</label>
            <input id="confirm_password" type="password" required value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="field-input mt-1" />
          </div>
          <button type="submit" disabled={loading}
            className="btn btn-primary w-full">
            {loading ? 'Resetting...' : 'Reset password'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          <Link to="/login" className="text-primary-600 hover:underline">Back to login</Link>
        </p>
      </div>
    </div>
  )
}

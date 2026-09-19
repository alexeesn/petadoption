import { useState, FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Alert, FieldError } from '../components/UI'

export default function VerifyEmailPage() {
  const { verifyEmail } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  const [email, setEmail] = useState(initialEmail)
  const [otp, setOtp] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyEmail(email, otp)
      // Auto-login: token was stored by verifyEmail, go straight to the
      // pet browsing (preserving any pet the user was about to adopt).
      const petParam = searchParams.get('pet')
      setSuccess('Email verified successfully! Logging you in...')
      setTimeout(() => navigate(petParam ? `/pets/${petParam}` : '/pets'), 1200)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { error?: string } } }
      setError(anyErr?.response?.data?.error || 'Verification failed. Please check your code.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="auth-card">
        <h1 className="text-3xl font-extrabold text-primary-900 text-center">Verify your email</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Enter the 6-digit code we emailed to you to activate your account.
        </p>

        {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
        {success && <div className="mt-4"><Alert type="success">{success}</Alert></div>}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="field-label">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="field-input mt-1"
            />
            <FieldError id="email-error" />
          </div>
          <div>
            <label htmlFor="otp" className="field-label">Verification code</label>
            <input
              id="otp"
              type="text"
              inputMode="numeric"
              maxLength={6}
              required
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              className="field-input mt-1 tracking-widest"
            />
            <FieldError id="otp-error" />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? 'Verifying...' : 'Verify email'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          <Link to={email ? `/resend-otp?email=${encodeURIComponent(email)}` : '/resend-otp'} className="text-primary-600 hover:underline">Resend code</Link>
        </p>
      </div>
    </div>
  )
}

import { useState, FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { Alert } from '../components/UI'

export default function ResendOtpPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  const [email, setEmail] = useState(initialEmail)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post('/auth/resend-otp/', { email })
      setSuccess('A new verification code has been sent.')
      setTimeout(() => navigate(`/verify-email?email=${encodeURIComponent(email)}`), 1500)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { error?: string; message?: string } } }
      setError(anyErr?.response?.data?.error || anyErr?.response?.data?.message || 'Could not resend the code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-8">
        <h1 className="text-2xl font-bold text-stone-800 text-center">Resend verification code</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Enter your email and we&apos;ll send you a fresh verification code.
        </p>

        {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
        {success && <div className="mt-4"><Alert type="success">{success}</Alert></div>}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-stone-700">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-orange-600 text-white font-medium rounded-md hover:bg-orange-700 disabled:opacity-50"
          >
            {loading ? 'Sending...' : 'Send new code'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          <Link to="/verify-email" className="text-orange-600 hover:underline">Back to verification</Link>
        </p>
      </div>
    </div>
  )
}
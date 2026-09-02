import { useState, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import { Alert, FieldError } from '../components/UI'

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post('/auth/forgot-password/', { email })
      setSuccess("If an account exists for that email, a reset code has been sent.")
      setTimeout(() => navigate(`/reset-password?email=${encodeURIComponent(email)}`), 1500)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { error?: string } } }
      setError(anyErr?.response?.data?.error || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-8">
        <h1 className="text-2xl font-bold text-stone-800 text-center">Forgot password</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Enter your email and we&apos;ll send you a password reset code.
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
            <FieldError id="email-error" />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-orange-600 text-white font-medium rounded-md hover:bg-orange-700 disabled:opacity-50"
          >
            {loading ? 'Sending...' : 'Send reset code'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          <Link to="/login" className="text-orange-600 hover:underline">Back to login</Link>
        </p>
      </div>
    </div>
  )
}

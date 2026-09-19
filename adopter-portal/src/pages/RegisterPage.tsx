import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FormEvent, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Alert } from '../components/UI'
import GoogleSignInButton from '../components/GoogleSignInButton'

export default function RegisterPage() {
  const { register, loginWithGoogle } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    password_confirm: '',
  })
  const [error, setError] = useState<Record<string, string | string[]> | string>({})
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  const petParam = searchParams.get('pet')

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError({})
    setLoading(true)
    try {
      await register(form)
      navigate(petParam ? `/verify-email?email=${encodeURIComponent(form.email)}&pet=${petParam}` : `/verify-email?email=${encodeURIComponent(form.email)}`)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: Record<string, string | string[]> } }
      setError(anyErr?.response?.data || {})
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleCredential = async (credential: string) => {
    setGoogleLoading(true)
    try {
      await loginWithGoogle(credential)
      navigate(petParam ? `/pets/${petParam}` : '/pets')
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { error?: string } } }
      setError(anyErr?.response?.data?.error || 'Google sign-up failed. Please try again.')
    } finally {
      setGoogleLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="auth-card">
        <h1 className="text-3xl font-extrabold text-primary-900 text-center">Create an account</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Join us to start your pet adoption journey.
        </p>

        {typeof error === 'string' && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
        {typeof error === 'string' ? null : error['error'] && (
          <div className="mt-4"><Alert type="error">{error['error']}</Alert></div>
        )}

        <div className="mt-6">
          {googleLoading ? (
            <p className="text-center text-sm text-stone-500">Signing up with Google...</p>
          ) : (
            <GoogleSignInButton onCredential={handleGoogleCredential} onError={(msg) => setError(msg)} />
          )}
        </div>

        <div className="my-5 flex items-center gap-3" aria-hidden="true">
          <span className="h-px flex-1 bg-stone-200" />
          <span className="text-xs text-stone-500">or</span>
          <span className="h-px flex-1 bg-stone-200" />
        </div>

        <form onSubmit={handleSubmit} className="mt-2 space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="first_name" className="field-label">First name</label>
              <input
                id="first_name" name="first_name" type="text" required value={form.first_name}
                onChange={handleChange}
                className="field-input mt-1"
              />
            </div>
            <div>
              <label htmlFor="last_name" className="field-label">Last name</label>
              <input
                id="last_name" name="last_name" type="text" required value={form.last_name}
                onChange={handleChange}
                className="field-input mt-1"
              />
            </div>
          </div>
          <div>
            <label htmlFor="email" className="field-label">Email</label>
            <input
              id="email" name="email" type="email" required value={form.email}
              onChange={handleChange}
              className="field-input mt-1"
            />
            {typeof error !== 'string' && error['email'] && (
              <p className="mt-1 text-sm text-red-600" role="alert">{String(error['email'])}</p>
            )}
          </div>
          <div>
            <label htmlFor="password" className="field-label">Password</label>
            <input
              id="password" name="password" type="password" required minLength={8} value={form.password}
              onChange={handleChange}
              className="field-input mt-1"
            />
            {typeof error !== 'string' && error['password'] && (
              <p className="mt-1 text-sm text-red-600" role="alert">{String(error['password'])}</p>
            )}
          </div>
          <div>
            <label htmlFor="password_confirm" className="field-label">Confirm password</label>
            <input
              id="password_confirm" name="password_confirm" type="password" required value={form.password_confirm}
              onChange={handleChange}
              className="field-input mt-1"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 hover:underline font-medium">Log in</Link>
        </p>
      </div>
    </div>
  )
}

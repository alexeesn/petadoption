import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FormEvent, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Alert } from '../components/UI'

export default function RegisterPage() {
  const { register } = useAuth()
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError({})
    setLoading(true)
    try {
      await register(form)
      const petParam = searchParams.get('pet')
      navigate(petParam ? `/verify-email?email=${encodeURIComponent(form.email)}&pet=${petParam}` : `/verify-email?email=${encodeURIComponent(form.email)}`)
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: Record<string, string | string[]> } }
      setError(anyErr?.response?.data || {})
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-8">
        <h1 className="text-2xl font-bold text-stone-800 text-center">Create an account</h1>
        <p className="mt-2 text-sm text-stone-500 text-center">
          Join us to start your pet adoption journey.
        </p>

        {typeof error === 'string' && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
        {typeof error === 'string' ? null : error['error'] && (
          <div className="mt-4"><Alert type="error">{error['error']}</Alert></div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="first_name" className="block text-sm font-medium text-stone-700">First name</label>
              <input
                id="first_name" name="first_name" type="text" required value={form.first_name}
                onChange={handleChange}
                className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
            </div>
            <div>
              <label htmlFor="last_name" className="block text-sm font-medium text-stone-700">Last name</label>
              <input
                id="last_name" name="last_name" type="text" required value={form.last_name}
                onChange={handleChange}
                className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
            </div>
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-stone-700">Email</label>
            <input
              id="email" name="email" type="email" required value={form.email}
              onChange={handleChange}
              className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            {typeof error !== 'string' && error['email'] && (
              <p className="mt-1 text-sm text-red-600" role="alert">{String(error['email'])}</p>
            )}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-stone-700">Password</label>
            <input
              id="password" name="password" type="password" required minLength={8} value={form.password}
              onChange={handleChange}
              className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            {typeof error !== 'string' && error['password'] && (
              <p className="mt-1 text-sm text-red-600" role="alert">{String(error['password'])}</p>
            )}
          </div>
          <div>
            <label htmlFor="password_confirm" className="block text-sm font-medium text-stone-700">Confirm password</label>
            <input
              id="password_confirm" name="password_confirm" type="password" required value={form.password_confirm}
              onChange={handleChange}
              className="mt-1 w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-orange-600 text-white font-medium rounded-md hover:bg-orange-700 disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          Already have an account?{' '}
          <Link to="/login" className="text-orange-600 hover:underline font-medium">Log in</Link>
        </p>
      </div>
    </div>
  )
}

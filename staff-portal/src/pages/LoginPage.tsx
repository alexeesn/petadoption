import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/UI';
import GoogleSignInButton from '../components/GoogleSignInButton';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(email, password);
      if (user.role === 'adopter') {
        setError('This account does not have staff access.');
        return;
      }
      navigate('/');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string; detail?: string } } };
      setError(axiosErr.response?.data?.error || axiosErr.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleCredential = async (credential: string) => {
    setGoogleLoading(true);
    setError('');
    try {
      const user = await loginWithGoogle(credential);
      if (user.role === 'adopter') {
        setError('This account does not have staff access. Google accounts are created as adopters only.');
        return;
      }
      navigate('/');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string; detail?: string } } };
      setError(axiosErr.response?.data?.error || axiosErr.response?.data?.detail || 'Google sign-in failed. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="bg-white p-8 rounded-lg shadow">
      <h2 className="text-xl font-bold text-slate-900 mb-6 text-center">Sign In</h2>
      {error && (
        <div className="mb-4 p-3 rounded-md bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="mb-4">
        {googleLoading ? (
          <p className="text-sm text-slate-500">Signing in with Google...</p>
        ) : (
          <GoogleSignInButton onCredential={handleGoogleCredential} onError={setError} />
        )}
      </div>

      <div className="mb-5 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-slate-200" />
        <span className="text-xs text-slate-400">or sign in with email</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="block text-sm font-medium text-slate-700 mb-1">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Email"
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-slate-700 mb-1">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Password"
          />
        </label>
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? 'Signing in...' : 'Sign In'}
        </Button>
      </form>
    </div>
  );
}

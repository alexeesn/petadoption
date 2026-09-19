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
  const { login, loginWithGoogle, logout } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(email, password);
      if (user.role === 'adopter') {
        await logout();
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
        await logout();
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
    <div className="panel p-8">
      <h2 className="mb-6 text-2xl font-bold text-primary-900">Sign In</h2>
      {error && (
        <div className="relative mb-4 overflow-hidden rounded-md border border-red-200 bg-red-50 py-3 pl-5 pr-4 text-sm text-red-800" role="alert">
          <span className="absolute inset-y-0 left-0 w-1.5 bg-red-600" aria-hidden="true" />
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
          <span className="field-label mb-1">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="field-input"
            aria-label="Email"
          />
        </label>
        <label className="block">
          <span className="field-label mb-1">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="field-input"
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

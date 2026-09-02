import { createContext, useContext, useState, ReactNode } from 'react';
import type { User } from '../types';
import { login as loginRequest, logout as logoutRequest, getStoredUser, getStoredToken } from '../services/apiService';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isStaff: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser());
  const [token, setToken] = useState<string | null>(getStoredToken());

  const login = async (email: string, password: string) => {
    const u = await loginRequest(email, password);
    setUser(u);
    setToken(getStoredToken());
    return u;
  };

  const logout = async () => {
    await logoutRequest();
    setUser(null);
    setToken(null);
  };

  const isAuthenticated = !!user && !!token;
  const isStaff = !!user && (user.role === 'staff' || user.role === 'admin');
  const isAdmin = !!user && user.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, isStaff, isAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

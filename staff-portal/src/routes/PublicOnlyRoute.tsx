import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isStaff } = useAuth();
  if (isAuthenticated && isStaff) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

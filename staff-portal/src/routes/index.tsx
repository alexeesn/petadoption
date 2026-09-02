import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { PublicLayout } from '../layouts/PublicLayout';
import { ProtectedRoute } from './ProtectedRoute';
import { PublicOnlyRoute } from './PublicOnlyRoute';
import LoginPage from '../pages/LoginPage';
import DashboardPage from '../pages/DashboardPage';
import ApplicationsPage from '../pages/ApplicationsPage';
import ApplicationDetailPage from '../pages/ApplicationDetailPage';
import PetsPage from '../pages/PetsPage';
import AdoptersPage from '../pages/AdoptersPage';
import DocumentsPage from '../pages/DocumentsPage';
import ReviewsPage from '../pages/ReviewsPage';
import HealthRecordsPage from '../pages/HealthRecordsPage';
import AdoptionsPage from '../pages/AdoptionsPage';
import PackagesPage from '../pages/PackagesPage';
import PaymentsPage from '../pages/PaymentsPage';
import ReportsPage from '../pages/ReportsPage';

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <PublicOnlyRoute>
              <PublicLayout>
                <LoginPage />
              </PublicLayout>
            </PublicOnlyRoute>
          }
        />
        <Route
          element={
            <ProtectedRoute>
              <DashboardLayout>
                <Outlet />
              </DashboardLayout>
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/applications/:id" element={<ApplicationDetailPage />} />
          <Route path="/pets" element={<PetsPage />} />
          <Route path="/adopters" element={<AdoptersPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/reviews" element={<ReviewsPage />} />
          <Route path="/health" element={<HealthRecordsPage />} />
          <Route path="/adoptions" element={<AdoptionsPage />} />
          <Route path="/packages" element={<PackagesPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

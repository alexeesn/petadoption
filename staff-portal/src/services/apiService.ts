import api from './api';
import type { User, PaginatedResponse } from '../types';

export async function login(email: string, password: string) {
  const res = await api.post('/auth/login/', { email, password });
  const { token, user } = res.data as { token: string; user: User };
  localStorage.setItem('staff_auth_token', token);
  localStorage.setItem('staff_auth_user', JSON.stringify(user));
  return user;
}

export async function loginWithGoogle(credential: string) {
  const res = await api.post('/auth/google/', { credential });
  const { token, user } = res.data as { token: string; user: User };
  localStorage.setItem('staff_auth_token', token);
  localStorage.setItem('staff_auth_user', JSON.stringify(user));
  return user;
}

export async function logout() {
  try {
    await api.post('/auth/logout/');
  } catch {
    // ignore
  }
  localStorage.removeItem('staff_auth_token');
  localStorage.removeItem('staff_auth_user');
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem('staff_auth_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem('staff_auth_token');
}

// ----- Dashboard statistics -----
export async function getDashboardStats() {
  const [apps, pets, adopters, adoptions] = await Promise.all([
    api.get('/applications/'),
    api.get('/pets/'),
    api.get('/adopters/'),
    api.get('/adoptions/'),
  ]);
  const appsRes = apps.data as PaginatedResponse<any>;
  const petsRes = pets.data as PaginatedResponse<any>;
  const adoptersRes = adopters.data as PaginatedResponse<any>;
  const adoptionsRes = adoptions.data as PaginatedResponse<any>;
  return {
    totalApplications: appsRes.count,
    totalPets: petsRes.count,
    totalAdopters: adoptersRes.count,
    totalAdoptions: adoptionsRes.count,
    recentApplications: appsRes.results.slice(0, 5),
  };
}

// ----- Applications -----
export const applicationService = {
  list: (params?: Record<string, unknown>) => api.get('/applications/', { params }),
  retrieve: (id: string) => api.get(`/applications/${id}/`),
  updateStatus: (id: string, data: Record<string, unknown>) =>
    api.post(`/applications/${id}/update-status/`, data),
};

// ----- Pets -----
export const petService = {
  list: (params?: Record<string, unknown>) => api.get('/pets/', { params }),
  retrieve: (id: string) => api.get(`/pets/${id}/`),
  create: (data: Record<string, unknown>) => api.post('/pets/', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/pets/${id}/`, data),
  remove: (id: string) => api.delete(`/pets/${id}/`),
};

// ----- Adopters -----
export const adopterService = {
  list: (params?: Record<string, unknown>) => api.get('/adopters/', { params }),
  retrieve: (id: string) => api.get(`/adopters/${id}/`),
};

// ----- Documents -----
export const documentService = {
  list: (params?: Record<string, unknown>) => api.get('/documents/', { params }),
  remove: (id: string) => api.delete(`/documents/${id}/`),
  downloadUrl: (id: string) => `${(import.meta.env.VITE_API_BASE_URL as string) || '/api'}/documents/${id}/download/`,
};

// ----- Reviews -----
export const reviewService = {
  list: (params?: Record<string, unknown>) => api.get('/reviews/', { params }),
  create: (data: Record<string, unknown>) => api.post('/reviews/', data),
};

// ----- Health Records -----
export const healthService = {
  list: (params?: Record<string, unknown>) => api.get('/health-records/', { params }),
  create: (data: Record<string, unknown>) => api.post('/health-records/', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/health-records/${id}/`, data),
  remove: (id: string) => api.delete(`/health-records/${id}/`),
  vaccinations: (params?: Record<string, unknown>) => api.get('/health-records/vaccinations/', { params }),
};

// ----- Adoptions -----
export const adoptionService = {
  list: (params?: Record<string, unknown>) => api.get('/adoptions/', { params }),
  create: (data: Record<string, unknown>) => api.post('/adoptions/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/adoptions/${id}/`, data),
  retrieve: (id: string) => api.get(`/adoptions/${id}/`),
};

// ----- Packages -----
export const packageService = {
  list: (params?: Record<string, unknown>) => api.get('/packages/', { params }),
  create: (data: Record<string, unknown>) => api.post('/packages/', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/packages/${id}/`, data),
  remove: (id: string) => api.delete(`/packages/${id}/`),
};

// ----- Payments -----
export const paymentService = {
  list: (params?: Record<string, unknown>) => api.get('/payments/', { params }),
  create: (data: Record<string, unknown>) => api.post('/payments/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/payments/${id}/`, data),
};

// ----- Reports -----
export const reportService = {
  adoption: (params?: Record<string, unknown>) => api.get('/reports/adoptions/', { params }),
  petInventory: (params?: Record<string, unknown>) => api.get('/reports/pets/', { params }),
  adopter: (params?: Record<string, unknown>) => api.get('/reports/adopters/', { params }),
  application: (params?: Record<string, unknown>) => api.get('/reports/applications/', { params }),
  health: (params?: Record<string, unknown>) => api.get('/reports/health/', { params }),
  payment: (params?: Record<string, unknown>) => api.get('/reports/payments/', { params }),
  csv: (reportType: string, params?: Record<string, unknown>) => {
    const urlMap: Record<string, string> = {
      adoption: '/reports/adoptions/',
      'pet-inventory': '/reports/pets/',
      adopter: '/reports/adopters/',
      application: '/reports/applications/',
      health: '/reports/health/',
      payment: '/reports/payments/',
    };
    const url = urlMap[reportType] || `/reports/${reportType}/`;
    return api.get(url, { params: { ...params, export: 'csv' }, responseType: 'blob' });
  },
};

// ----- Notifications -----
export const notificationService = {
  list: (params?: Record<string, unknown>) => api.get('/notifications/', { params }),
  markRead: (id: string) => api.patch(`/notifications/${id}/`, { is_read: true }),
};

// ----- Audit Logs (Admin only) -----
export const auditService = {
  list: (params?: Record<string, unknown>) => api.get('/audit/', { params }),
};

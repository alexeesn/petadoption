import api from './api';
import type { User, Notification, PaginatedResponse } from '../types';

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
  // Fee totals and turnover eligibility for the onsite workflow (read-only
  // summary; the backend is the source of truth for fee/paid/eligibility).
  paymentSummary: (id: string) => api.get(`/applications/${id}/payment-summary/`),
  updateStatus: (id: string, data: Record<string, unknown>) =>
    api.post(`/applications/${id}/update-status/`, data),
  update: (id: string, data: Record<string, unknown>) =>
    api.patch(`/applications/${id}/`, data),
  // Completes the onsite adoption. The API only accepts this when the
  // application is approved, the appointment is confirmed, the onsite
  // payment has been recorded, and the staff member explicitly confirms
  // that the pet was physically handed over (confirmed: true).  The
  // confirmation checkbox on the application detail page is the UI that
  // produces this flag; the backend re-validates it and rejects anything
  // that is not an actual boolean true.
  completeAdoption: (id: string, notes = '') =>
    api.post(`/applications/${id}/complete-adoption/`, {
      notes,
      confirmed: true,
    }),
};

// ----- Pets -----
export const petService = {
  list: (params?: Record<string, unknown>) => api.get('/pets/', { params }),
  retrieve: (id: string) => api.get(`/pets/${id}/`),
  // FormData uploads must send multipart; the shared axios instance defaults
  // to application/json, which would JSON-stringify the FormData in axios 1.x.
  create: (data: Record<string, unknown> | FormData) =>
    api.post('/pets/', data, data instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined),
  // PATCH so editing only the fields sent by the Edit Pet form leaves every
  // other pet field (status, weight, ...) untouched. Photos live on their own
  // endpoint and are therefore never affected by a pet information update.
  update: (id: string, data: Record<string, unknown>) => api.patch(`/pets/${id}/`, data),
  remove: (id: string) => api.delete(`/pets/${id}/`),
  // Existing pet photo architecture: one file per request. Adding or removing
  // one photo never touches the pet's other photos.
  addImage: (petId: string, file: File) => {
    const fd = new FormData();
    fd.append('image', file);
    return api.post(`/pets/${petId}/images/`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
  },
  removeImage: (petId: string, imageId: string) =>
    api.delete(`/pets/${petId}/images/${imageId}/`),
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
  // Documents are private: the file has to be fetched with the auth token, so
  // a plain <a href="..."> is refused (it cannot send the Authorization
  // header). Always go through these helpers instead.
  download: (id: string) => api.get(`/documents/${id}/download/`, { responseType: 'blob' }),
};

/** Opens a private document in a new tab (browser previews PDFs and images). */
export async function openDocument(id: string) {
  const res = await documentService.download(id);
  const url = URL.createObjectURL(res.data as Blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Saves a private document to disk using its original filename. */
export async function saveDocument(id: string, filename: string) {
  const res = await documentService.download(id);
  const url = URL.createObjectURL(res.data as Blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || 'document';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

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
  cancel: (id: string, reason: string) => api.post(`/adoptions/${id}/cancel/`, { reason, confirmed: true }),
  list: (params?: Record<string, unknown>) => api.get('/adoptions/', { params }),
  create: (data: Record<string, unknown>) => api.post('/adoptions/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/adoptions/${id}/`, data),
  retrieve: (id: string) => api.get(`/adoptions/${id}/`),
  // Staff-only PDF export matching the active ?status= filter. The backend
  // renders the whole matching set server-side (not just the current page) and
  // returns an application/pdf blob with a Content-Disposition attachment name.
  exportPdf: (params?: Record<string, unknown>) =>
    api.get('/adoptions/export-pdf/', { params, responseType: 'blob' }),
  // Individual adoption record PDF for one completed adoption (staff-only).
  recordPdf: (id: string) =>
    api.get(`/adoptions/${id}/record-pdf/`, { responseType: 'blob' }),
};

// ----- Appointments (onsite visit dates) -----
export const appointmentService = {
  markNoShow: (id: string, reason: string) => api.post(`/appointments/${id}/mark-no-show/`, { reason, confirmed: true }),
  list: (params?: Record<string, unknown>) => api.get('/appointments/', { params }),
  retrieve: (id: string) => api.get(`/appointments/${id}/`),
  // Appointment decisions are explicit actions (the API does not accept PATCH).
  approve: (id: string) => api.post(`/appointments/${id}/approve/`),
  reject: (id: string, reason: string) => api.post(`/appointments/${id}/reject/`, { reason }),
};

// ----- Packages -----
export const rescheduleService = {
  list: (params?: Record<string, unknown>) => api.get('/appointments/reschedule-requests/', { params }),
  approve: (id: string) => api.post(`/appointments/reschedule-requests/${id}/approve/`, { confirmed: true }),
  reject: (id: string, reason: string) => api.post(`/appointments/reschedule-requests/${id}/reject/`, { reason, confirmed: true }),
};

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
  // Staff-only on-site payment recording. The backend forces status=completed,
  // generates the receipt number, and never trusts client-supplied status or
  // receipt values — the UI only sends what was actually received.
  recordOnsite: (data: Record<string, unknown>) => api.post('/payments/record-onsite/', data),
  // Staff-only PDF export matching the active ?status=/?application= filters.
  // The backend renders the report server-side for the whole matching set (not
  // just the current pagination page) and the response is an application/pdf
  // blob with a Content-Disposition attachment filename.
  exportPdf: (params?: Record<string, unknown>) =>
    api.get('/payments/export-pdf/', { params, responseType: 'blob' }),
  // Individual receipt PDF for one payment transaction (staff-only).
  receiptPdf: (id: string) =>
    api.get(`/payments/${id}/receipt-pdf/`, { responseType: 'blob' }),
};

// ----- Reports -----
export const reportService = {
  adoption: (params?: Record<string, unknown>) => api.get('/reports/adoptions/', { params }),
  petInventory: (params?: Record<string, unknown>) => api.get('/reports/pets/', { params }),
  adopter: (params?: Record<string, unknown>) => api.get('/reports/adopters/', { params }),
  application: (params?: Record<string, unknown>) => api.get('/reports/applications/', { params }),
  health: (params?: Record<string, unknown>) => api.get('/reports/health/', { params }),
  payment: (params?: Record<string, unknown>) => api.get('/reports/payments/', { params }),
  monthlyPaymentsPdf: (year: number, month: number) =>
    api.get('/reports/monthly-payments-pdf/', { params: { year, month }, responseType: 'blob' }),
  monthlyAdoptionsPdf: (year: number, month: number) =>
    api.get('/reports/monthly-adoptions-pdf/', { params: { year, month }, responseType: 'blob' }),
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
  unreadCount: () => api.get('/notifications/unread-count/'),
  markAllRead: () => api.post('/notifications/mark-all-read/'),
  list: (params?: Record<string, unknown>) => api.get('/notifications/', { params }),
  // Unread notifications of the authenticated user, following the existing
  // `?unread=true` filter and pagination (PAGE_SIZE = 20) so counts are not
  // silently capped at the first page.
  listUnread: async (): Promise<Notification[]> => {
    const collected: Notification[] = [];
    // Bounded loop: a guard against a malformed `next` link, never hit in practice.
    for (let page = 1; page <= 10; page += 1) {
      const res = await api.get('/notifications/', { params: { unread: true, page } });
      const data = res.data as PaginatedResponse<Notification> | Notification[];
      if (Array.isArray(data)) {
        collected.push(...data);
        break;
      }
      collected.push(...data.results);
      if (!data.next) break;
    }
    return collected;
  },
  // Existing backend endpoint (PATCH /api/notifications/<id>/read/): sets
  // is_read on that one notification for the authenticated user. It never
  // touches application/appointment/payment records.
  markRead: (id: string) => api.patch(`/notifications/${id}/read/`, {}),
};

// ----- Audit Logs (Admin only) -----
export const auditService = {
  list: (params?: Record<string, unknown>) => api.get('/audit/', { params }),
};

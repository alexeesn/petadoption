import api from '../../services/api'
import type { SurrenderPage, SurrenderRequest } from './types'

export const surrenderService = {
  list: async (page: number, status: string) => (await api.get<SurrenderPage>('/surrenders/', { params: { page, ...(status ? { status } : {}) } })).data,
  get: async (id: string) => (await api.get<SurrenderRequest>(`/surrenders/${id}/`)).data,
  create: async (data: FormData) => (await api.post<SurrenderRequest>('/surrenders/', data, { headers: { 'Content-Type': 'multipart/form-data' } })).data,
  resubmit: async (id: string, data: FormData) => (await api.post<SurrenderRequest>(`/surrenders/${id}/resubmit/`, data, { headers: { 'Content-Type': 'multipart/form-data' } })).data,
  action: async (id: string, action: string, data: Record<string, unknown> = {}) => (await api.post<SurrenderRequest>(`/surrenders/${id}/${action}/`, data)).data,
  photo: async (id: string, photoId: string) => (await api.get<Blob>(`/surrenders/${id}/photos/${photoId}/`, { responseType: 'blob' })).data,
}

export function surrenderError(error: unknown) {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data
  if (!data) return 'Unable to save. Check your connection and try again.'
  return Object.entries(data).map(([key, value]) => `${key.replace(/_/g, ' ')}: ${Array.isArray(value) ? value.join(' ') : String(value)}`).join(' · ')
}

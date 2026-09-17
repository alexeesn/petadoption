import api from '../services/api'

export async function fetchPets(params?: Record<string, string>) {
  const { data } = await api.get('/pets/', { params })
  return data
}

export async function fetchPet(id: string) {
  const { data } = await api.get(`/pets/${id}/`)
  return data
}

export async function fetchApplications() {
  const { data } = await api.get('/applications/')
  return data
}

export async function fetchApplication(id: string) {
  const { data } = await api.get(`/applications/${id}/`)
  return data
}

export interface ApplicationDocumentUpload {
  document_type: string
  file: File
}

/**
 * Submits the application and its documents in a single request, so the
 * documents are stored with the application the moment it is submitted.
 */
export async function createApplication(
  petId: string,
  details: Record<string, unknown>,
  documents: ApplicationDocumentUpload[] = []
) {
  const formData = new FormData()
  formData.append('pet', petId)
  Object.entries(details).forEach(([key, value]) => {
    formData.append(key, typeof value === 'boolean' ? String(value) : String(value ?? ''))
  })
  documents.forEach((doc) => {
    formData.append('documents', doc.file)
    formData.append('document_types', doc.document_type)
  })
  const { data } = await api.post('/applications/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function cancelApplication(id: string) {
  const { data } = await api.post(`/applications/${id}/cancel/`)
  return data
}

export async function fetchDocuments(applicationId?: string) {
  const { data } = await api.get('/documents/', { params: applicationId ? { application_id: applicationId } : {} })
  return data
}

export async function uploadDocument(applicationId: string, file: File, documentType: string) {
  const formData = new FormData()
  formData.append('application', applicationId)
  formData.append('document_type', documentType)
  formData.append('file', file)
  const { data } = await api.post('/documents/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteDocument(id: string) {
  await api.delete(`/documents/${id}/`)
}

export async function fetchNotifications() {
  const { data } = await api.get('/notifications/')
  return data
}

export async function markNotificationRead(id: string) {
  await api.patch(`/notifications/${id}/read/`, { is_read: true })
}

export async function markAllNotificationsRead() {
  await api.post('/notifications/mark-all-read/')
}

export async function fetchAdoptionRecords() {
  const { data } = await api.get('/adoptions/')
  return data
}

export async function fetchAdoptionRecord(id: string) {
  const { data } = await api.get(`/adoptions/${id}/`)
  return data
}

export async function fetchAdopterProfile() {
  const { data } = await api.get('/adopters/profile/')
  return data
}

export async function updateAdopterProfile(profile: Record<string, string | number | boolean>) {
  const { data } = await api.patch('/adopters/profile/', profile)
  return data
}

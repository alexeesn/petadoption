import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('pam_token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

// Handle 401 - clear token and redirect
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pam_token')
      localStorage.removeItem('pam_user')
    }
    return Promise.reject(error)
  }
)

export default api

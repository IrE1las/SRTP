import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('railway_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.code === 'ERR_CANCELED') return Promise.reject(error)
    const status = error.response?.status
    const message = error.response?.data?.detail || '请求失败，请稍后重试'

    if (status === 401) {
      localStorage.removeItem('railway_access_token')
      localStorage.removeItem('railway_user')
      if (window.location.pathname !== '/login') {
        ElMessage.error('登录已失效，请重新登录')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request

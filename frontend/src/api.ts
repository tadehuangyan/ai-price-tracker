import axios from 'axios'
import router from './router'

const api = axios.create({
  // 相对路径 + Vite 代理转发到后端，页面与接口同源，局域网/内网穿透均可访问
  baseURL: '/',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('spt_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('spt_token')
      localStorage.removeItem('spt_user')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export function errMsg(e: any): string {
  return e?.response?.data?.detail || e?.message || '请求失败'
}

export default api

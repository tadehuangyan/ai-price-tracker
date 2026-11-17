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
  // detail 可能是字符串，也可能是校验错误数组/对象——必须归一为字符串，
  // 否则传给 ElMessage 会被当作配置对象导致提示渲染崩溃（表现为“点击无响应”）
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d) return d
  if (Array.isArray(d)) {
    return d.map((x: any) => x?.msg || x?.detail || '').filter(Boolean).join('；') || '请求参数有误'
  }
  if (d && typeof d === 'object') return String(d.msg || d.message || '请求失败')
  return e?.message || '请求失败'
}

export default api

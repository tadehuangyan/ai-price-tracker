/**
 * 封装后端 API 调用：提供统一的 axios 实例（自动携带登录令牌、统一处理 401），
 * 以及把接口异常归一为中文提示文本的工具函数。
 */
import axios from 'axios'
import router from './router'

const api = axios.create({
  // 相对路径 + Vite 代理转发到后端，页面与接口同源，局域网/内网穿透均可访问
  baseURL: '/',
  timeout: 30000,
})

// 请求拦截器：本地存有登录令牌时自动附加到请求头，实现接口鉴权
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('spt_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器：401（未登录或令牌失效）时清除本地登录态并跳转登录页
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

/** 将接口异常归一为可直接展示的中文错误提示文本 */
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

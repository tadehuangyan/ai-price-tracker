/**
 * 全局状态管理（Pinia）：保存用户登录态与权限信息，登录信息持久化到 localStorage 以便刷新后恢复。
 */
import { defineStore } from 'pinia'

// 用户基本信息（登录成功后由后端返回）
export interface UserInfo {
  id: number
  username: string
  nickname: string
  email: string
  role: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    // token / user 初始值从 localStorage 恢复，保证刷新页面后登录态不丢失
    token: localStorage.getItem('spt_token') || '',
    user: JSON.parse(localStorage.getItem('spt_user') || 'null') as UserInfo | null,
  }),
  getters: {
    // 是否已登录 / 是否为管理员（路由守卫与页面权限判断使用）
    isLogin: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    // 登录：写入登录态并同步持久化到 localStorage
    login(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem('spt_token', token)
      localStorage.setItem('spt_user', JSON.stringify(user))
    },
    // 登出：清空登录态并移除本地存档
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('spt_token')
      localStorage.removeItem('spt_user')
    },
  },
})

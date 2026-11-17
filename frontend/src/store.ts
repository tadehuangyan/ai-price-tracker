import { defineStore } from 'pinia'

export interface UserInfo {
  id: number
  username: string
  nickname: string
  email: string
  role: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('spt_token') || '',
    user: JSON.parse(localStorage.getItem('spt_user') || 'null') as UserInfo | null,
  }),
  getters: {
    isLogin: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    login(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem('spt_token', token)
      localStorage.setItem('spt_user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('spt_token')
      localStorage.removeItem('spt_user')
    },
  },
})

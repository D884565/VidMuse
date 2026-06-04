import { defineStore } from 'pinia'
import { login, logout } from '@/api/modules/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    userInfo: JSON.parse(localStorage.getItem('userInfo') || '{}')
  }),

  actions: {
    async login(username, password) {
      try {
        const res = await login({ username, password })
        const { token, userInfo } = res.data
        this.token = token
        this.userInfo = userInfo
        localStorage.setItem('token', token)
        localStorage.setItem('userInfo', JSON.stringify(userInfo))
        return Promise.resolve()
      } catch (error) {
        return Promise.reject(error)
      }
    },

    async logout() {
      try {
        await logout()
      } finally {
        this.token = ''
        this.userInfo = {}
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
      }
    }
  }
})

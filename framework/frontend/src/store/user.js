import { defineStore } from 'pinia'

import { getCurrentUser, login as loginApi } from '@/api/auth'

const TOKEN_KEY = 'railway_access_token'
const USER_KEY = 'railway_user'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '',
    user: null,
  }),
  getters: {
    role: (state) => state.user?.role || '',
    isLoggedIn: (state) => Boolean(state.token && state.user),
    isStudent: (state) => state.user?.role === 'student',
    isTeacher: (state) => state.user?.role === 'teacher',
    isAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    restoreAuth() {
      const token = localStorage.getItem(TOKEN_KEY)
      const storedUser = localStorage.getItem(USER_KEY)
      if (!token || !storedUser) {
        return
      }

      try {
        this.token = token
        this.user = JSON.parse(storedUser)
      } catch {
        this.clearAuth()
      }
    },
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    clearAuth() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
    async login(payload) {
      const response = await loginApi(payload)
      this.setAuth(response.access_token, response.user)
      return response.user
    },
    async fetchProfile() {
      const user = await getCurrentUser()
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      return user
    },
    logout() {
      this.clearAuth()
    },
  },
})

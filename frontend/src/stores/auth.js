import { defineStore } from 'pinia'
import { api, getToken, setToken } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: getToken(),
    ready: false, // becomes true once the initial /me check completes
  }),

  getters: {
    isAuthed: (s) => !!s.token && !!s.user,
    // Elevated roles: admin and super_admin both pass owner-or-admin gates.
    isAdmin: (s) => ['admin', 'super_admin'].includes(s.user?.role),
    isSuperAdmin: (s) => s.user?.role === 'super_admin',
    // Advisory only — backend re-checks every request. Used to hide UI.
    hasPermission: (s) => (perm) => {
      const perms = s.user?.permissions || []
      return perms.includes('*') || perms.includes(perm)
    },
    initials: (s) => (s.user?.name || '?').trim().slice(0, 2).toUpperCase(),
  },

  actions: {
    async restore() {
      // Validate an existing token on app boot.
      if (!this.token) {
        this.ready = true
        return
      }
      try {
        const { user } = await api.me()
        this.user = user
      } catch {
        this.logout()
      } finally {
        this.ready = true
      }
    },

    async login(email, password) {
      const { token, user } = await api.login({ email, password })
      this._apply(token, user)
    },

    async register(payload) {
      const { token, user } = await api.register(payload)
      this._apply(token, user)
    },

    _apply(token, user) {
      this.token = token
      this.user = user
      setToken(token)
    },

    logout() {
      this.token = null
      this.user = null
      setToken(null)
    },
  },
})

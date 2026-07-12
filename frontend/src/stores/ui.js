import { defineStore } from 'pinia'

let toastId = 0

// Theme + transient UI state (toasts). Theme choice is persisted.
export const useUiStore = defineStore('ui', {
  state: () => ({
    theme: 'light',
    toasts: [],
  }),

  getters: {
    isDark: (s) => s.theme === 'dark',
  },

  actions: {
    initTheme() {
      const saved = localStorage.getItem('mml.theme')
      const prefersDark =
        window.matchMedia?.('(prefers-color-scheme: dark)').matches
      this.setTheme(saved || (prefersDark ? 'dark' : 'light'))
    },

    setTheme(theme) {
      this.theme = theme
      document.documentElement.dataset.theme = theme
      localStorage.setItem('mml.theme', theme)
    },

    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },

    toast(message, type = 'success', timeout = 3200) {
      const id = ++toastId
      this.toasts.push({ id, message, type, timeout })
      if (timeout) setTimeout(() => this.dismiss(id), timeout)
      return id
    },
    success(m) { return this.toast(m, 'success') },
    error(m) { return this.toast(m, 'error', 5000) },

    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id)
    },
  },
})

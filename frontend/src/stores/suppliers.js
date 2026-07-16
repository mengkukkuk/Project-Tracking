// Supplier directory store — backs the BOM page's supplier info card.
// Loads the whole (small) directory once; matching the free-text supplier
// string on BOM/inventory rows to a profile happens client-side, mirroring
// stores/lookups.js's fetch-once pattern.
import { defineStore } from 'pinia'
import { api } from '@/api'

const norm = (s) => String(s || '').trim().toLowerCase()

export const useSuppliersStore = defineStore('suppliers', {
  state: () => ({
    items: [],
    loading: false,
    error: null,
  }),

  getters: {
    // BOM rows store free text ("KEYENCE", "Mitsubishi"/"MITSUBISHI"…), so the
    // lookup is case-insensitive against both the short code and the full name.
    byLabel: (state) => (label) => {
      const needle = norm(label)
      if (!needle) return null
      return (
        state.items.find((s) => norm(s.code) === needle || norm(s.name) === needle) || null
      )
    },
  },

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const res = await api.listSuppliers()
        this.items = res.items || []
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})

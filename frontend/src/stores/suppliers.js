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

    // Create/update are admin-gated on the backend; both keep `items` sorted
    // by name so the list stays consistent with fetchAll's server order.
    async createRow(payload) {
      const row = await api.createSupplier(payload)
      this.items = [...this.items, row].sort((a, b) => (a.name || '').localeCompare(b.name || ''))
      return row
    },

    async updateRow(id, payload) {
      const row = await api.updateSupplier(id, payload)
      this.items = this.items.map((s) => (s.id === id ? row : s))
      return row
    },
  },
})

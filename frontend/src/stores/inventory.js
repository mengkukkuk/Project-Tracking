// Inventory catalogue store — the pool BomListPicker.vue builds lists from.
// Read-only: the catalogue is managed via SQL/seed, so there are no CRUD
// actions here (unlike stores/bom.js, which backs the editable /bom page).
import { defineStore } from 'pinia'
import { api } from '@/api'

export const useInventoryStore = defineStore('inventory', {
  state: () => ({
    rows: [],
    loading: false,
    error: null,
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const res = await api.listInventory()
        this.rows = res.items || []
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})

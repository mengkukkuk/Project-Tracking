// Inventory catalogue store — the pool BomListPicker.vue builds lists from,
// and the data source behind the BOM page's INVENTORY toggle. Writes hit the
// capability-gated endpoints (create: any user; update/delete: admin) and
// mutate `rows` in place so the grid and the picker stay in sync without a
// refetch.
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

    async createRow(payload) {
      const row = await api.createInventory(payload)
      this.rows = [row, ...this.rows]
      return row
    },

    async updateRow(id, payload) {
      const row = await api.updateInventory(id, payload)
      this.rows = this.rows.map((r) => (r.id === id ? { ...r, ...row } : r))
      return row
    },

    async deleteRow(id) {
      await api.deleteInventory(id)
      this.rows = this.rows.filter((r) => r.id !== id)
    },
  },
})

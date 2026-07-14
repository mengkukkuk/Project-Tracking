// Lookup taxonomy store — backs the BOM page's Category -> Type cascading
// filter. Loads the whole (small) types->values tree once; cascading happens
// entirely client-side, mirroring stores/bom.js's fetch-once pattern.
import { defineStore } from 'pinia'
import { api } from '@/api'

export const useLookupsStore = defineStore('lookups', {
  state: () => ({
    types: [],
    loading: false,
    error: null,
  }),

  getters: {
    typeByCode: (state) => (code) => state.types.find((t) => t.code === code) || null,
  },

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const res = await api.listLookups()
        this.types = res.types || []
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})

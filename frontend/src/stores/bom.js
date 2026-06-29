// Global BOM store — backs the top-level BOM page (BomGlobalView.vue).
// Lists every bom_and_costing row across all projects, with client-side text
// search. Inline edit/delete reuse the per-project record endpoints.
import { defineStore } from 'pinia'
import { api } from '@/api'
import { useProjectsStore } from '@/stores/projects'

export const useBomStore = defineStore('bom', {
  state: () => ({
    rows: [],
    loading: false,
    error: null,
    q: '',
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const res = await api.listBomAll()
        this.rows = res.items || []
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    setQuery(v) {
      this.q = v
    },

    async createRow(projectId, payload) {
      // POST returns a bare to_dict() WITHOUT projectName. Look it up from the
      // projects store so the new row renders the Project column without a
      // round-trip refetch.
      const resp = await api.createRecord(projectId, 'bom', payload)
      const projectsStore = useProjectsStore()
      const proj = projectsStore.projects.find((p) => p.id === projectId)
      const newRow = { ...resp, projectName: proj?.name || '' }
      this.rows = [newRow, ...this.rows]
    },

    async updateRow(id, payload) {
      // PATCH returns a bare to_dict() WITHOUT projectName — merge into the
      // existing row so the join-derived Project column survives the edit.
      const resp = await api.updateRecord('bom', id, payload)
      this.rows = this.rows.map((r) => (r.id === id ? { ...r, ...resp } : r))
    },

    async deleteRow(id) {
      await api.deleteRecord('bom', id)
      this.rows = this.rows.filter((r) => r.id !== id)
    },
  },
})

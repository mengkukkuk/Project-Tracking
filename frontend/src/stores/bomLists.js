// Saved BOM lists — backs BomListsManager.vue and BomListPicker.vue.
// State is intentionally minimal: a `lists` array (summary form) for the
// manager and a `current` object (detail form, includes items[]) for the
// picker in edit mode.
import { defineStore } from 'pinia'
import { api } from '@/api'

export const useBomListsStore = defineStore('bomLists', {
  state: () => ({
    lists: [],
    current: null,
    loading: false,
    error: null,
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const res = await api.listBomLists()
        this.lists = res.items || []
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async fetchOne(id) {
      const detail = await api.getBomList(id)
      this.current = detail
      return detail
    },

    async create(payload) {
      const resp = await api.createBomList(payload)
      // Prepend the new summary; detail is fetched on demand by the picker.
      this.lists = [resp, ...this.lists]
      return resp
    },

    async update(id, payload) {
      // PATCH returns the summary form. Merge into the existing row so any
      // client-side fields stay, and clear `current` so the picker re-fetches
      // detail if reopened.
      const resp = await api.updateBomList(id, payload)
      this.lists = this.lists.map((l) => (l.id === id ? { ...l, ...resp } : l))
      this.current = null
      return resp
    },

    async remove(id) {
      await api.deleteBomList(id)
      this.lists = this.lists.filter((l) => l.id !== id)
      if (this.current?.id === id) this.current = null
    },
  },
})

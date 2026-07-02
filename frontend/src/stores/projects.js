import { defineStore } from 'pinia'
import { api } from '@/api'
import { useUiStore } from '@/stores/ui'

export const STAGES = [
  'Pre-Sale',
  'Project Initiation',
  'award',
  'Project Delivery',
  'Completed',
]

// Progress is derived from the process checklist (ptrack): checked / total.
// Every project (list row or detail) carries processCount/processDone, kept
// fresh by _syncProcessCounts, so this stays live as the checklist is toggled.
// Falls back to the Task-entity counts for projects with no process checklist.
export function taskProgress(p) {
  const ptotal = p?.processCount || 0
  if (ptotal) return Math.round(((p.processDone || 0) / ptotal) * 100)
  const total = p?.taskCount || 0
  return total ? Math.round(((p.taskDone || 0) / total) * 100) : 0
}

export const useProjectsStore = defineStore('projects', {
  state: () => ({
    projects: [],
    stats: null,
    loading: false,
    error: null,
    filters: { q: '', status: '', domain: '', priority: '', fiscalYear: '' },
    // detail drawer
    current: null,
    detailLoading: false,
    // per-project auxiliary records, keyed by resource name
    records: {},
    recordsLoading: false,
  }),

  getters: {
    byStage: (s) => {
      const map = Object.fromEntries(STAGES.map((st) => [st, []]))
      for (const p of s.projects) (map[p.status] ??= []).push(p)
      return map
    },

    // Group projects by project manager. Primary source is the multi-PM
    // relation (`pms` from the users table); falls back to the legacy free-text
    // `pm` field for projects that predate multi-PM, and an "Unassigned" bucket
    // for projects with neither. A project with several PMs appears in each of
    // their groups. Returns an array of { key, id, name, projects }.
    byPm: (s) => {
      const map = new Map()
      const ensure = (key, id, name) => {
        if (!map.has(key)) map.set(key, { key, id, name, projects: [] })
        return map.get(key)
      }
      for (const p of s.projects) {
        if (p.pms && p.pms.length) {
          for (const u of p.pms) ensure(`u:${u.id}`, u.id, u.name).projects.push(p)
        } else if (p.pm && p.pm.trim()) {
          ensure(`t:${p.pm.trim()}`, null, p.pm.trim()).projects.push(p)
        } else {
          ensure('__none__', null, 'Unassigned').projects.push(p)
        }
      }
      return [...map.values()].sort((a, b) => {
        if (a.key === '__none__') return 1
        if (b.key === '__none__') return -1
        return a.name.localeCompare(b.name)
      })
    },

    kpis: (s) => {
      const total = s.projects.reduce((a, p) => a + (p.value || 0), 0)
      const pipeline = s.projects
        .filter((p) => p.status !== 'Completed')
        .reduce((a, p) => a + (p.value || 0), 0)
      return {
        totalProjects: s.projects.length,
        totalValue: total,
        pipelineValue: pipeline,
        inDelivery: s.projects.filter((p) => p.status === 'Project Delivery').length,
        completed: s.projects.filter((p) => p.status === 'Completed').length,
      }
    },

    funnel: (s) =>
      STAGES.map((stage) => {
        const items = s.projects.filter((p) => p.status === stage)
        return {
          stage,
          count: items.length,
          value: items.reduce((a, p) => a + (p.value || 0), 0),
        }
      }),

    fiscalBreakdown: (s) => {
      const years = {}
      for (const p of s.projects) {
        const fy = p.fiscalYear || 'future'
        years[fy] ??= Object.fromEntries(STAGES.map((st) => [st, 0]))
        if (STAGES.includes(p.status)) years[fy][p.status] += 1
      }
      const order = ['69', '70', '71', 'future']
      return Object.keys(years)
        .sort((a, b) => order.indexOf(a) - order.indexOf(b))
        .map((fy) => ({ fy, ...years[fy] }))
    },

    domainBreakdown: (s) => {
      const m = {}
      for (const p of s.projects) {
        const d = p.domain || 'อื่นๆ'
        m[d] = (m[d] || 0) + 1
      }
      return Object.entries(m).map(([name, value]) => ({ name, value }))
    },
  },

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        const [list, stats] = await Promise.all([
          api.listProjects(this.filters),
          api.stats(),
        ])
        this.projects = list.items
        this.stats = stats
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    setFilter(patch) {
      Object.assign(this.filters, patch)
      return this.fetchAll()
    },

    clearFilters() {
      this.filters = { q: '', status: '', domain: '', priority: '', fiscalYear: '' }
      return this.fetchAll()
    },

    _upsert(project) {
      const i = this.projects.findIndex((x) => x.id === project.id)
      // Replace the array reference (not in-place) so @tanstack/vue-table, which
      // memoizes its row model by data identity, rebuilds and re-runs accessors
      // (e.g. the task-derived progress column) without a manual refresh.
      if (i !== -1) {
        const next = this.projects.slice()
        // Keep the lightweight list shape; detail payloads carry extra keys.
        next[i] = { ...next[i], ...project }
        this.projects = next
      } else {
        this.projects = [project, ...this.projects]
      }
    },

    async createProject(data) {
      const created = await api.createProject(data)
      this._upsert(created)
      await this.refreshStats()
      useUiStore().success('สร้างโครงการแล้ว')
      return created
    },

    async updateProject(id, patch) {
      const updated = await api.updateProject(id, patch)
      this._upsert(updated)
      if (this.current?.id === id) this.current = updated
      await this.refreshStats()
      return updated
    },

    async deleteProject(id) {
      await api.deleteProject(id)
      this.projects = this.projects.filter((p) => p.id !== id)
      if (this.current?.id === id) this.current = null
      await this.refreshStats()
      useUiStore().success('ลบโครงการแล้ว')
    },

    async refreshStats() {
      try {
        this.stats = await api.stats()
      } catch (e) {
        if (import.meta.env.DEV) console.warn('[refreshStats]', e)
      }
    },

    // --- Detail drawer ---
    async openDetail(id) {
      this.detailLoading = true
      this.current = null
      this.records = {}
      try {
        this.current = await api.getProject(id)
      } catch (e) {
        useUiStore().error(e.message)
      } finally {
        this.detailLoading = false
      }
    },

    closeDetail() {
      this.current = null
      this.records = {}
    },

    // --- Per-project auxiliary records ---
    async fetchRecords(resource) {
      if (!this.current) return
      this.recordsLoading = true
      try {
        const res = await api.listRecords(this.current.id, resource)
        this.records = { ...this.records, [resource]: res.items }
      } catch (e) {
        useUiStore().error(e.message)
      } finally {
        this.recordsLoading = false
      }
    },

    async addRecord(resource, data) {
      const created = await api.createRecord(this.current.id, resource, data)
      const list = this.records[resource] || []
      this.records = { ...this.records, [resource]: [...list, created] }
      return created
    },

    async editRecord(resource, id, data) {
      const updated = await api.updateRecord(resource, id, data)
      const list = (this.records[resource] || []).map((r) => (r.id === id ? updated : r))
      this.records = { ...this.records, [resource]: list }
      return updated
    },

    async removeRecord(resource, id) {
      await api.deleteRecord(resource, id)
      const list = (this.records[resource] || []).filter((r) => r.id !== id)
      this.records = { ...this.records, [resource]: list }
    },

    // --- Process checklist (ptrack) ---
    // Optimistic toggle of a ptrack row's checked state, mirroring toggleTask:
    // flip immediately so the checklist + progress bar update on the same frame,
    // then reconcile with the server. Roll back on failure.
    async toggleProcess(rec) {
      const prev = rec.checked
      rec.checked = !prev
      this._syncProcessCounts()
      try {
        const updated = await api.updateRecord('ptrack', rec.id, { checked: rec.checked })
        Object.assign(rec, updated)
        this._syncProcessCounts()
      } catch (e) {
        rec.checked = prev
        this._syncProcessCounts()
        throw e
      }
    },

    _syncProcessCounts() {
      if (!this.current) return
      const rows = this.records['ptrack'] || []
      const counts = {
        processCount: rows.length,
        processDone: rows.filter((r) => r.checked).length,
      }
      // Keep the open detail object live and upsert the lightweight list row so
      // the task-derived progress bar (detail, table, cards) updates immediately.
      Object.assign(this.current, counts)
      this._upsert({ id: this.current.id, ...counts })
    },

    // Backfill a project's process checklist from the template (older projects
    // predate the create-time seed), then load the rows.
    async generateProcess(pid) {
      const updated = await api.generatePtrack(pid)
      if (this.current?.id === pid) this.current = updated
      this._upsert(updated)
      await this.fetchRecords('ptrack')
    },

    async addTask(pid, data) {
      const task = await api.createTask(pid, data)
      if (this.current?.id === pid) this.current.tasks.push(task)
      this._syncTaskCounts(pid)
      return task
    },

    // Optimistic toggle: flip immediately so the checklist + progress bar update
    // on the same frame, then reconcile with the server. Roll back on failure.
    async toggleTask(task) {
      const prev = task.done
      task.done = !prev
      this._syncTaskCounts(task.projectId)
      try {
        const updated = await api.updateTask(task.id, { done: task.done })
        Object.assign(task, updated)
        this._syncTaskCounts(task.projectId)
      } catch (e) {
        task.done = prev
        this._syncTaskCounts(task.projectId)
        throw e
      }
    },

    async deleteTask(task) {
      await api.deleteTask(task.id)
      if (this.current) this.current.tasks = this.current.tasks.filter((t) => t.id !== task.id)
      this._syncTaskCounts(task.projectId)
    },

    _syncTaskCounts(pid) {
      if (!this.current || this.current.id !== pid) return
      const tasks = this.current.tasks
      const counts = {
        taskCount: tasks.length,
        taskDone: tasks.filter((t) => t.done).length,
      }
      // Keep the open detail object live too, so the checklist header and the
      // task-derived progress bar update immediately when tasks are toggled.
      Object.assign(this.current, counts)
      this._upsert({ id: pid, ...counts })
    },

    async addComment(pid, body) {
      const comment = await api.createComment(pid, { body })
      if (this.current?.id === pid) this.current.comments.unshift(comment)
      return comment
    },

    async deleteComment(pid, cid) {
      await api.deleteComment(cid)
      if (this.current?.id === pid)
        this.current.comments = this.current.comments.filter((c) => c.id !== cid)
    },

    async exportToSheets() {
      const ui = useUiStore()
      try {
        const result = await api.sheetsExport()
        ui.success(`ส่งออก ${result.exported} โครงการไปยัง Google Sheets แล้ว`)
        return result
      } catch (e) {
        ui.error(e.message)
        throw e
      }
    },

    async importFromSheets(preview = false) {
      const ui = useUiStore()
      try {
        const result = await api.sheetsImport(preview)
        if (!preview) {
          ui.success(`นำเข้า ${result.created} โครงการจาก Google Sheets แล้ว`)
          await this.fetchAll()
        }
        return result
      } catch (e) {
        ui.error(e.message)
        throw e
      }
    },
  },
})

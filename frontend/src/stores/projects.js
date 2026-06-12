import { defineStore } from 'pinia'
import { api } from '@/api'
import { useUiStore } from '@/stores/ui'

export const STAGES = [
  'Pre-Sale',
  'Project Initiation',
  'Award',
  'Project Delivery',
  'Completed',
]

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
  }),

  getters: {
    byStage: (s) => {
      const map = Object.fromEntries(STAGES.map((st) => [st, []]))
      for (const p of s.projects) (map[p.status] ??= []).push(p)
      return map
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
      // Keep the lightweight list shape; detail payloads carry extra keys.
      if (i !== -1) this.projects[i] = { ...this.projects[i], ...project }
      else this.projects.unshift(project)
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

    // Optimistic Kanban move with rollback.
    async moveProject(id, newStatus) {
      const p = this.projects.find((x) => x.id === id)
      if (!p || p.status === newStatus) return
      const prev = p.status
      p.status = newStatus
      try {
        const updated = await api.updateProject(id, { status: newStatus })
        this._upsert(updated)
        await this.refreshStats()
      } catch (e) {
        p.status = prev
        useUiStore().error(e.message)
      }
    },

    async refreshStats() {
      try {
        this.stats = await api.stats()
      } catch { /* non-fatal */ }
    },

    // --- Detail drawer ---
    async openDetail(id) {
      this.detailLoading = true
      this.current = null
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
    },

    async addTask(pid, data) {
      const task = await api.createTask(pid, data)
      if (this.current?.id === pid) this.current.tasks.push(task)
      this._syncTaskCounts(pid)
      return task
    },

    async toggleTask(task) {
      const updated = await api.updateTask(task.id, { done: !task.done })
      Object.assign(task, updated)
      this._syncTaskCounts(task.projectId)
    },

    async deleteTask(task) {
      await api.deleteTask(task.id)
      if (this.current) this.current.tasks = this.current.tasks.filter((t) => t.id !== task.id)
      this._syncTaskCounts(task.projectId)
    },

    _syncTaskCounts(pid) {
      if (!this.current || this.current.id !== pid) return
      const tasks = this.current.tasks
      this._upsert({
        id: pid,
        taskCount: tasks.length,
        taskDone: tasks.filter((t) => t.done).length,
      })
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
  },
})

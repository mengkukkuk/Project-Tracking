<script setup>
import { useProjectsStore } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import ProjectCard from '@/components/ProjectCard.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'

const store = useProjectsStore()
const { baht, daysUntil } = useFormat()

function colTotal(projects) {
  return projects.reduce((a, p) => a + (p.value || 0), 0)
}

function colRisk(projects) {
  return {
    overdue: projects.filter((p) => {
      const due = daysUntil(p.dueDate)
      return due != null && due < 0 && p.status !== 'Completed'
    }).length,
    critical: projects.filter((p) => p.priority === 'critical').length,
  }
}

function initials(name) {
  const parts = (name || '?').trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">People board</div>
        <h1 class="page-title">PM cards</h1>
        <p class="page-subtitle">Every project grouped by its project manager — one card per PM.</p>
      </div>
    </header>

    <ProjectFilters compact />

    <div v-if="store.byPm.length" class="board">
      <div class="board-inner">
      <div v-for="pm in store.byPm" :key="pm.key" class="column">
        <div class="col-head" :class="{ unassigned: pm.key === '__none__' }">
          <div class="col-title">
            <span class="avatar" :class="{ ghost: pm.key === '__none__' }">{{ initials(pm.name) }}</span>
            <span class="pm-name" :title="pm.name">{{ pm.name }}</span>
          </div>
          <div class="col-meta">
            <span class="count">{{ pm.projects.length }} project{{ pm.projects.length === 1 ? '' : 's' }}</span>
            <span class="sum mono">{{ baht(colTotal(pm.projects)) }}</span>
          </div>
          <div v-if="colRisk(pm.projects).overdue || colRisk(pm.projects).critical" class="risk-line">
            <span v-if="colRisk(pm.projects).overdue" class="risk danger">{{ colRisk(pm.projects).overdue }} overdue</span>
            <span v-if="colRisk(pm.projects).critical" class="risk warn">{{ colRisk(pm.projects).critical }} critical</span>
          </div>
        </div>

        <div class="col-body">
          <div v-for="p in pm.projects" :key="p.id" class="card-wrap">
            <ProjectCard :project="p" @open="store.openDetail" />
          </div>
          <div v-if="!pm.projects.length" class="col-empty">No projects</div>
        </div>
      </div>
      </div>
    </div>

    <div v-else class="empty-board">No projects match the current filters.</div>
  </div>
</template>

<style scoped>
/* Scrollbar-on-top: flip the scroll container, flip the inner wrapper back so
   content stays upright while the native horizontal scrollbar renders above
   the cards. Reset on mobile (vertical stack + sticky headers). */
.board { overflow-x: auto; transform: rotateX(180deg); }
.board-inner { display: flex; gap: 14px; padding-bottom: 12px; align-items: start; transform: rotateX(180deg); }
.column { display: flex; flex-direction: column; flex: 1 0 264px; max-width: 360px; min-width: 0; }
.col-head { background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--accent); border-radius: 8px 8px 0 0; padding: 11px 13px; }
.col-head.unassigned { border-top-color: var(--text-dim); }
.col-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
.avatar {
  width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 10px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0;
}
.avatar.ghost { background: var(--text-dim); }
.pm-name { font-size: 13px; font-weight: 700; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-meta { display: flex; justify-content: space-between; gap: 10px; margin-top: 8px; }
.count { font-size: 11px; color: var(--text-dim); }
.sum { font-size: 12px; color: var(--text-dim); }
.risk-line { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.risk { font-size: 10px; font-weight: 700; border-radius: 6px; padding: 2px 6px; }
.risk.danger { color: var(--danger); background: var(--critical-bg); }
.risk.warn { color: var(--warning); background: var(--warning-bg); }
.col-body { background: var(--bg-sunken); border: 1px solid var(--border); border-top: none; border-radius: 0 0 8px 8px; padding: 10px; flex: 1; min-height: 160px; display: flex; flex-direction: column; gap: 9px; }
.col-empty { text-align: center; color: var(--text-dim); font-size: 12px; padding: 20px 0; border: 1px dashed var(--border); border-radius: 8px; }
.empty-board { padding: 60px; text-align: center; color: var(--text-dim); border: 1px dashed var(--border); border-radius: 8px; }

@media (max-width: 760px) {
  .board { overflow-x: visible; transform: none; }
  .board-inner { flex-direction: column; padding-bottom: 0; transform: none; }
  .column { width: 100%; max-width: none; flex: none; }
  .col-head { position: sticky; top: 56px; z-index: 5; border-radius: 8px 8px 0 0; }
  .col-body { min-height: 80px; padding: 10px; }
  .col-body:has(.col-empty) { min-height: 64px; padding: 8px; }
  .col-empty { padding: 12px 0; }
}
</style>

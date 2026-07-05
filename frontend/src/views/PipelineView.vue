<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectsStore, STAGES } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import { STAGE_COLORS } from '@/composables/useChartTheme'
import ProjectCard from '@/components/ProjectCard.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'

const store = useProjectsStore()
const route = useRoute()
const router = useRouter()
const { baht, daysUntil } = useFormat()

// The URL is the source of truth for grouping mode, so the toggle state is
// shareable/bookmarkable and survives back/forward navigation. Anything
// other than 'pm' (including an absent param) resolves to 'status'.
const mode = computed({
  get: () => (route.query.group === 'pm' ? 'pm' : 'status'),
  set: (value) => {
    router.replace({ query: { ...route.query, group: value === 'pm' ? 'pm' : undefined } })
  },
})

function initials(name) {
  const parts = (name || '?').trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

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

// Normalized column shape so the template only needs one v-for loop,
// regardless of which store getter produced the grouping.
const columns = computed(() => {
  if (mode.value === 'status') {
    const grouped = store.byStage
    return STAGES.map((stage) => ({
      key: stage,
      label: stage,
      projects: grouped[stage] || [],
      dotColor: STAGE_COLORS[stage],
      avatarText: null,
      isUnassigned: false,
    }))
  }
  return store.byPm.map((pm) => ({
    key: pm.key,
    label: pm.name,
    projects: pm.projects,
    dotColor: null,
    avatarText: initials(pm.name),
    isUnassigned: pm.key === '__none__',
  }))
})
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">{{ mode === 'pm' ? 'Project managers view' : 'Pipeline view' }}</div>
        <h1 class="page-title">Pipeline</h1>
        <p class="page-subtitle">
          {{ mode === 'pm' ? 'จัดกลุ่ม Project ตามผู้รับผิดชอบ' : 'จัดกลุ่ม Project ตามสถานะ' }}
        </p>
      </div>
      <div class="segmented" aria-label="Group by">
        <button type="button" :class="{ active: mode === 'status' }" @click="mode = 'status'">Status</button>
        <button type="button" :class="{ active: mode === 'pm' }" @click="mode = 'pm'">PMs</button>
      </div>
    </header>

    <ProjectFilters compact />

    <div v-if="columns.length" class="board">
      <div class="board-inner" :class="mode === 'status' ? 'by-status' : 'by-pm'">
        <div v-for="col in columns" :key="col.key" class="column">
          <div
            class="col-head"
            :class="{ unassigned: col.isUnassigned }"
            :style="col.dotColor ? { borderTopColor: col.dotColor } : null"
          >
            <div class="col-title">
              <span v-if="col.dotColor" class="dot" :style="{ background: col.dotColor }" />
              <span v-else class="avatar" :class="{ ghost: col.isUnassigned }">{{ col.avatarText }}</span>
              <span class="col-label" :title="col.label">{{ col.label }}</span>
            </div>
            <div class="col-meta">
              <span class="count">{{ col.projects.length }} project{{ col.projects.length === 1 ? '' : 's' }}</span>
              <span class="sum mono">{{ baht(colTotal(col.projects)) }}</span>
            </div>
            <div v-if="colRisk(col.projects).overdue || colRisk(col.projects).critical" class="risk-line">
              <span v-if="colRisk(col.projects).overdue" class="risk danger">{{ colRisk(col.projects).overdue }} overdue</span>
              <span v-if="colRisk(col.projects).critical" class="risk warn">{{ colRisk(col.projects).critical }} critical</span>
            </div>
          </div>

          <div class="col-body">
            <div v-for="element in col.projects" :key="element.id" class="card-wrap">
              <ProjectCard :project="element" @open="store.openDetail" />
            </div>
            <div v-if="!col.projects.length" class="col-empty">
              {{ mode === 'pm' ? 'No projects' : 'No projects in this stage' }}
            </div>
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
.board-inner.by-status { display: grid; grid-template-columns: repeat(5, minmax(240px, 1fr)); }
.board-inner.by-pm .column { flex: 1 0 264px; max-width: 360px; }

.column { display: flex; flex-direction: column; min-width: 0; }
.col-head {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent);
  border-radius: 14px 14px 0 0;
  padding: 11px 13px;
  background:
    radial-gradient(130% 90% at 100% -10%, var(--accent-soft), transparent 55%),
    linear-gradient(180deg, var(--lc-sheen-top), var(--lc-sheen-mid) 32%),
    var(--lc-base);
  -webkit-backdrop-filter: blur(var(--lc-blur)) saturate(165%);
  backdrop-filter: blur(var(--lc-blur)) saturate(165%);
  box-shadow: inset 0 1px 0 var(--lc-inner-sheen), var(--lc-float);
}
.col-head::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: linear-gradient(180deg, var(--lc-rim-bright), var(--lc-rim-fade) 18%, var(--lc-rim-end) 46%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask-composite: exclude;
  pointer-events: none;
  z-index: 0;
}
.col-head.unassigned { border-top-color: var(--text-dim); }
.col-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
.dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.avatar {
  width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 10px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0;
}
.avatar.ghost { background: var(--text-dim); }
.col-label { font-size: 13px; font-weight: 700; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-meta { display: flex; justify-content: space-between; gap: 10px; margin-top: 6px; }
.count { font-size: 11px; color: var(--text-dim); }
.sum { font-size: 12px; color: var(--text-dim); }
.risk-line { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.risk {
  font-size: 10px;
  font-weight: 700;
  border-radius: 6px;
  padding: 2px 6px;
}
.risk.danger { color: var(--danger); background: var(--critical-bg); }
.risk.warn { color: var(--warning); background: var(--warning-bg); }
.col-body { background: var(--bg-sunken); border: 1px solid var(--border); border-top: none; border-radius: 0 0 14px 14px; padding: 10px; flex: 1; min-height: 160px; display: flex; flex-direction: column; gap: 9px; }
.col-empty { text-align: center; color: var(--text-dim); font-size: 12px; padding: 20px 0; border: 1px dashed var(--border); border-radius: 8px; }
.empty-board { padding: 60px; text-align: center; color: var(--text-dim); border: 1px dashed var(--border); border-radius: 8px; }

.segmented { display: inline-flex; padding: 3px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); flex-shrink: 0; }
.segmented button {
  border: 0;
  background: transparent;
  color: var(--text-dim);
  border-radius: 6px;
  min-height: 28px;
  padding: 0 11px;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color .12s, background .12s;
}
.segmented button.active { background: var(--accent); color: #fff; }

@media (max-width: 960px) {
  .board-inner.by-status { grid-template-columns: repeat(5, minmax(230px, 270px)); }
}
@media (max-width: 760px) {
  .board { overflow-x: visible; transform: none; }
  .board-inner {
    flex-direction: column;
    gap: 14px;
    padding-bottom: 0;
    transform: none;
  }
  .board-inner.by-status { display: flex; }
  .column { width: 100%; }
  .board-inner.by-pm .column { width: 100%; max-width: none; flex: none; }
  .col-head {
    position: sticky;
    top: 56px;
    z-index: 5;
    border-radius: 14px 14px 0 0;
    /* near-opaque so cards scrolling underneath don't bleed through */
    background:
      radial-gradient(130% 90% at 100% -10%, var(--accent-soft), transparent 55%),
      linear-gradient(180deg, var(--lc-sheen-top), var(--lc-sheen-mid) 32%),
      var(--lc-base-strong);
  }
  .col-body {
    min-height: 80px;
    padding: 10px;
  }
  /* Collapse column body when empty to save vertical space */
  .col-body:has(.col-empty) { min-height: 64px; padding: 8px; }
  .col-empty { padding: 12px 0; }
}
</style>

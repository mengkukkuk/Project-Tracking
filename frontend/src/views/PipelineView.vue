<script setup>
import { reactive, watch } from 'vue'
import { useProjectsStore, STAGES } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import { STAGE_COLORS } from '@/composables/useChartTheme'
import ProjectCard from '@/components/ProjectCard.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'

const store = useProjectsStore()
const { baht, daysUntil } = useFormat()

const cols = reactive(Object.fromEntries(STAGES.map((s) => [s, []])))

function rebuild() {
  const grouped = store.byStage
  for (const s of STAGES) cols[s] = [...(grouped[s] || [])]
}
watch(() => store.projects, rebuild, { immediate: true, deep: false })

// Drag-to-change-status is disabled: project status is now derived from the
// process-checklist progress %, so users can't move it directly. The board
// remains grouped-by-stage for read-only inspection.

function colTotal(stage) {
  return cols[stage].reduce((a, p) => a + (p.value || 0), 0)
}

function colRisk(stage) {
  const rows = cols[stage]
  return {
    overdue: rows.filter((p) => {
      const due = daysUntil(p.dueDate)
      return due != null && due < 0 && p.status !== 'Completed'
    }).length,
    critical: rows.filter((p) => p.priority === 'critical').length,
  }
}
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Pipeline view</div>
        <h1 class="page-title">Pipeline</h1>
        <p class="page-subtitle">จัดกลุ่ม Project ตามสถานะ</p>
      </div>
    </header>

    <ProjectFilters compact />

    <div class="board">
      <div class="board-inner">
      <div v-for="stage in STAGES" :key="stage" class="column">
        <div class="col-head" :style="{ borderTopColor: STAGE_COLORS[stage] }">
          <div class="col-title">
            <span class="dot" :style="{ background: STAGE_COLORS[stage] }" />
            {{ stage }}
          </div>
          <div class="col-meta">
            <span class="count">{{ cols[stage].length }} projects</span>
            <span class="sum mono">{{ baht(colTotal(stage)) }}</span>
          </div>
          <div v-if="colRisk(stage).overdue || colRisk(stage).critical" class="risk-line">
            <span v-if="colRisk(stage).overdue" class="risk danger">{{ colRisk(stage).overdue }} overdue</span>
            <span v-if="colRisk(stage).critical" class="risk warn">{{ colRisk(stage).critical }} critical</span>
          </div>
        </div>

        <div class="col-body">
          <div v-for="element in cols[stage]" :key="element.id" class="card-wrap">
            <ProjectCard :project="element" @open="store.openDetail" />
          </div>
          <div v-if="!cols[stage].length" class="col-empty">No projects in this stage</div>
        </div>
      </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scrollbar-on-top: flip the scroll container, flip the inner wrapper back so
   content stays upright while the native horizontal scrollbar renders above
   the cards. Reset on mobile (vertical stack + sticky headers). */
.board { overflow-x: auto; transform: rotateX(180deg); }
.board-inner { display: grid; grid-template-columns: repeat(5, minmax(240px, 1fr)); gap: 14px; padding-bottom: 12px; align-items: start; transform: rotateX(180deg); }
.column { display: flex; flex-direction: column; min-width: 0; }
.col-head { background: var(--surface); border: 1px solid var(--border); border-top: 3px solid; border-radius: 8px 8px 0 0; padding: 11px 13px; }
.col-title { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 700; color: var(--text); }
.dot { width: 7px; height: 7px; border-radius: 50%; }
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
.col-body { background: var(--bg-sunken); border: 1px solid var(--border); border-top: none; border-radius: 0 0 8px 8px; padding: 10px; flex: 1; min-height: 160px; display: flex; flex-direction: column; gap: 9px; }
.ghost { opacity: .4; }
.col-empty { text-align: center; color: var(--text-dim); font-size: 12px; padding: 20px 0; border: 1px dashed var(--border); border-radius: 8px; }
@media (max-width: 960px) {
  .board-inner { grid-template-columns: repeat(5, minmax(230px, 270px)); }
}
@media (max-width: 760px) {
  .board { overflow-x: visible; transform: none; }
  .board-inner {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-bottom: 0;
    transform: none;
  }
  .column { width: 100%; }
  .col-head {
    position: sticky;
    top: 56px;
    z-index: 5;
    border-radius: 8px 8px 0 0;
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

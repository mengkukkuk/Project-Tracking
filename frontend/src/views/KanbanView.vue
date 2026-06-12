<script setup>
import { reactive, watch } from 'vue'
import draggable from 'vuedraggable'
import { useProjectsStore, STAGES } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import { STAGE_COLORS } from '@/composables/useChartTheme'
import ProjectCard from '@/components/ProjectCard.vue'

const store = useProjectsStore()
const { baht } = useFormat()

// Local, drag-mutable mirror of the store's grouping. Rebuilt whenever the
// underlying projects change (create / move / delete / filter).
const cols = reactive(Object.fromEntries(STAGES.map((s) => [s, []])))

function rebuild() {
  const grouped = store.byStage
  for (const s of STAGES) cols[s] = [...(grouped[s] || [])]
}
watch(() => store.projects, rebuild, { immediate: true, deep: false })

function onChange(stage, evt) {
  if (evt.added) store.moveProject(evt.added.element.id, stage)
}

function colTotal(stage) {
  return cols[stage].reduce((a, p) => a + (p.value || 0), 0)
}

let t
function onSearch(e) {
  clearTimeout(t)
  const v = e.target.value
  t = setTimeout(() => store.setFilter({ q: v }), 300)
}
</script>

<template>
  <div class="view">
    <header class="top">
      <h1 class="page-title">บอร์ดงาน (Kanban)</h1>
      <input class="input search" placeholder="ค้นหาโครงการ..." :value="store.filters.q" @input="onSearch" />
    </header>

    <div class="board">
      <div v-for="stage in STAGES" :key="stage" class="column">
        <div class="col-head" :style="{ borderTopColor: STAGE_COLORS[stage] }">
          <div class="col-title">
            <span class="dot" :style="{ background: STAGE_COLORS[stage] }" />
            {{ stage }}
          </div>
          <div class="col-meta">
            <span class="count">{{ cols[stage].length }} โครงการ</span>
            <span class="sum mono">{{ baht(colTotal(stage)) }}</span>
          </div>
        </div>

        <draggable
          v-model="cols[stage]"
          group="projects"
          item-key="id"
          class="col-body"
          ghost-class="ghost"
          :animation="160"
          @change="(e) => onChange(stage, e)"
        >
          <template #item="{ element }">
            <div class="card-wrap">
              <ProjectCard :project="element" @open="store.openDetail" />
            </div>
          </template>
          <template #footer>
            <div v-if="!cols[stage].length" class="col-empty">ลากการ์ดมาที่นี่</div>
          </template>
        </draggable>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 12px; flex-wrap: wrap; }
.search { max-width: 260px; }
.board { display: grid; grid-template-columns: repeat(5, minmax(230px, 1fr)); gap: 14px; overflow-x: auto; padding-bottom: 12px; align-items: start; }
.column { display: flex; flex-direction: column; }
.col-head { background: var(--surface); border: 1px solid var(--border); border-top: 3px solid; border-radius: 9px 9px 0 0; padding: 11px 13px; }
.col-title { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 600; color: var(--text); }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.col-meta { display: flex; justify-content: space-between; margin-top: 6px; }
.count { font-size: 11px; color: var(--text-dim); }
.sum { font-size: 12px; color: var(--text-dim); }
.col-body { background: var(--bg-sunken); border: 1px solid var(--border); border-top: none; border-radius: 0 0 9px 9px; padding: 10px; flex: 1; min-height: 120px; display: flex; flex-direction: column; gap: 9px; }
.ghost { opacity: .4; }
.col-empty { text-align: center; color: var(--text-dim); font-size: 12px; padding: 20px 0; border: 1px dashed var(--border); border-radius: 8px; }
</style>

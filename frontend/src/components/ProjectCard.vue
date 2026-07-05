<script setup>
import { computed } from 'vue'
import { useFormat } from '@/composables/useFormat'
import { DOMAIN_COLORS } from '@/composables/useChartTheme'
import { taskProgress } from '@/stores/projects'
import ProgressBar from './ProgressBar.vue'
import PriorityBadge from './PriorityBadge.vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({ project: Object })
defineEmits(['open'])
const { baht, daysUntil } = useFormat()

const due = computed(() => {
  const d = daysUntil(props.project.dueDate)
  if (d == null || props.project.status === 'Completed') return null
  if (d < 0) return { text: `${-d}d overdue`, cls: 'overdue' }
  if (d === 0) return { text: 'Due today', cls: 'soon' }
  if (d <= 7) return { text: `${d}d left`, cls: 'soon' }
  return null
})

const taskLabel = computed(() => {
  if (!props.project.taskCount) return 'No tasks'
  return `${props.project.taskDone}/${props.project.taskCount} tasks`
})
</script>

<template>
  <button class="pcard lc-lift" type="button" @click="$emit('open', project.id)">
    <span class="pcard-top">
      <span
        class="domain"
        :style="{ background: (DOMAIN_COLORS[project.domain] || '#64748b') + '22',
                  color: DOMAIN_COLORS[project.domain] || '#64748b' }"
      >{{ project.domain || 'Other' }}</span>
      <PriorityBadge :priority="project.priority" />
    </span>

    <span class="pname">{{ project.name }}</span>

    <span class="meta-line">
      <span class="avatar" :title="project.pm">{{ (project.pm || '?').slice(0, 1).toUpperCase() }}</span>
      <span class="cust">{{ project.customer || 'No customer' }}</span>
    </span>

    <span v-if="project.tags?.length" class="tags">
      <span v-for="t in project.tags.slice(0, 3)" :key="t.id" class="tag" :style="{ background: t.color + '22', color: t.color }">
        {{ t.name }}
      </span>
    </span>

    <span class="pcard-bottom">
      <span class="chip">
        <AppIcon name="check" :size="12" />
        {{ taskLabel }}
      </span>
      <span v-if="due" class="chip" :class="due.cls">
        <AppIcon name="clock" :size="12" />
        {{ due.text }}
      </span>
      <span class="value mono">{{ baht(project.value) }}</span>
    </span>

    <ProgressBar :value="taskProgress(project)" :height="4" />
  </button>
</template>

<style scoped>
/* Liquid-crystal card WITHOUT backdrop-filter: dozens render on the pipeline
   board and they sit on an opaque pool, so the blur is dropped for scroll perf
   while keeping the base/sheen/rim look. */
.pcard {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 8px;
  width: 100%;
  border-radius: var(--radius-lg);
  background:
    radial-gradient(130% 90% at 100% -10%, var(--accent-soft), transparent 55%),
    linear-gradient(180deg, var(--lc-sheen-top), var(--lc-sheen-mid) 32%),
    var(--lc-base);
  border: 1px solid var(--border);
  box-shadow: inset 0 1px 0 var(--lc-inner-sheen), var(--lc-float);
  padding: 11px 12px; cursor: pointer; text-align: left; font: inherit; color: var(--text);
  transition: box-shadow .3s ease, transform .3s ease, border-color .15s;
}
.pcard::before {
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
.pcard:hover { border-color: var(--accent); }
.pcard:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.pcard-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.domain { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 5px; }
.value { margin-left: auto; font-size: 12px; font-weight: 700; color: var(--text); }
.pname { font-size: 13px; font-weight: 700; color: var(--text); line-height: 1.35; }
.meta-line { display: flex; align-items: center; gap: 7px; min-width: 0; }
.avatar {
  width: 22px; height: 22px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 10px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0;
}
.cust { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: var(--text-dim); }
.tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 4px; }
.pcard-bottom { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-dim);
  background: var(--bg-sunken);
  padding: 2px 6px;
  border-radius: 6px;
}
.chip.overdue { color: var(--danger); background: var(--critical-bg); }
.chip.soon { color: var(--warning); background: var(--warning-bg); }
</style>

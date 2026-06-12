<script setup>
import { computed } from 'vue'
import { useFormat } from '@/composables/useFormat'
import { DOMAIN_COLORS } from '@/composables/useChartTheme'
import ProgressBar from './ProgressBar.vue'

const props = defineProps({ project: Object })
defineEmits(['open'])
const { baht, daysUntil } = useFormat()

const due = computed(() => {
  const d = daysUntil(props.project.dueDate)
  if (d == null || props.project.status === 'Completed') return null
  if (d < 0) return { text: `เกิน ${-d} วัน`, cls: 'overdue' }
  if (d <= 7) return { text: `อีก ${d} วัน`, cls: 'soon' }
  return null
})
</script>

<template>
  <div class="pcard" @click="$emit('open', project.id)">
    <div class="pcard-top">
      <span
        class="domain"
        :style="{ background: (DOMAIN_COLORS[project.domain] || '#64748b') + '22',
                  color: DOMAIN_COLORS[project.domain] || '#64748b' }"
      >{{ project.domain || '—' }}</span>
      <span class="value mono">{{ baht(project.value) }}</span>
    </div>

    <div class="pname">{{ project.name }}</div>

    <div v-if="project.tags?.length" class="tags">
      <span v-for="t in project.tags.slice(0, 3)" :key="t.id" class="tag" :style="{ background: t.color + '22', color: t.color }">
        {{ t.name }}
      </span>
    </div>

    <div class="pcard-bottom">
      <span class="avatar" :title="project.pm">{{ (project.pm || '?').slice(-1) }}</span>
      <span class="cust">{{ project.customer }}</span>
      <span v-if="project.taskCount" class="chip">✓ {{ project.taskDone }}/{{ project.taskCount }}</span>
      <span v-if="due" class="chip" :class="due.cls">⏱ {{ due.text }}</span>
    </div>

    <ProgressBar :value="project.progress" :height="3" />
  </div>
</template>

<style scoped>
.pcard {
  background: var(--surface); border: 1px solid var(--border); border-radius: 9px;
  padding: 11px 12px; cursor: pointer; transition: box-shadow .15s, transform .1s, border-color .15s;
}
.pcard:hover { box-shadow: var(--shadow-lg); border-color: var(--accent); }
.pcard-top { display: flex; justify-content: space-between; align-items: center; }
.domain { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 4px; }
.value { font-size: 12px; font-weight: 600; color: var(--text); }
.pname { font-size: 13px; font-weight: 500; color: var(--text); margin: 8px 0; line-height: 1.35; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.tag { font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.pcard-bottom { display: flex; align-items: center; gap: 6px; margin-bottom: 9px; flex-wrap: wrap; }
.avatar {
  width: 20px; height: 20px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 10px; font-weight: 600; display: grid; place-items: center; flex-shrink: 0;
}
.cust { font-size: 11px; color: var(--text-dim); margin-right: auto; }
.chip { font-size: 10px; color: var(--text-dim); background: var(--bg-sunken); padding: 1px 6px; border-radius: 5px; }
.chip.overdue { color: #ef4444; background: #fef2f2; }
.chip.soon { color: #f59e0b; background: #fffbeb; }
</style>

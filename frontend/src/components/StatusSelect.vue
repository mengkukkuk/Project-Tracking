<script setup>
import { ref, watch } from 'vue'
import { STAGES, useProjectsStore } from '@/stores/projects'

const props = defineProps({
  id: { type: [Number, String], required: true },
  status: { type: String, required: true },
})

const store = useProjectsStore()
const saving = ref(false)
// Local optimistic value: TanStack memoizes row.original, so the prop may not
// refresh after an in-place store upsert. Track the shown value locally and
// resync whenever the prop does change (e.g. after a full refetch).
const value = ref(props.status)
watch(() => props.status, (s) => { value.value = s })

const COLORS = {
  'Pre-Sale': ['#f59e0b', '#fef3c7'],
  'Project Initiation': ['#3b82f6', '#dbeafe'],
  award: ['#8b5cf6', '#ede9fe'],
  'Project Delivery': ['#14b8a6', '#ccfbf1'],
  Completed: ['#10b981', '#d1fae5'],
}

async function onChange(e) {
  const next = e.target.value
  if (next === value.value) return
  const prev = value.value
  value.value = next
  saving.value = true
  try {
    await store.updateProject(props.id, { status: next })
  } catch (err) {
    value.value = prev
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <span
    class="status-select"
    :style="{ color: COLORS[value]?.[0], background: COLORS[value]?.[1] }"
    @click.stop
  >
    <span class="dot" :style="{ background: COLORS[value]?.[0] }" />
    <select
      :value="value"
      :disabled="saving"
      aria-label="Project status"
      @click.stop
      @change="onChange"
    >
      <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
    </select>
  </span>
</template>

<style scoped>
.status-select {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex: none;
}
select {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  padding-right: 2px;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
}
select:disabled {
  cursor: progress;
}
select option {
  color: var(--text);
  background: var(--surface);
}
</style>

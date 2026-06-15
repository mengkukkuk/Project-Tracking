<script setup>
import { computed, ref, watch } from 'vue'
import { useProjectsStore, STAGES } from '@/stores/projects'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  compact: Boolean,
})

const store = useProjectsStore()
const q = ref(store.filters.q || '')

const DOMAINS = ['Vision Sensor', 'Robot', 'PLC', 'IoT', 'AI']
const PRIORITIES = [
  ['low', 'Low'],
  ['medium', 'Medium'],
  ['high', 'High'],
  ['critical', 'Critical'],
]
const FYS = [
  ['69', 'FY69'],
  ['70', 'FY70'],
  ['71', 'FY71'],
  ['future', 'Future'],
]

const savedViews = [
  { label: 'All', filters: { q: '', status: '', domain: '', priority: '', fiscalYear: '' } },
  { label: 'Pipeline', filters: { status: '', priority: '', fiscalYear: '' } },
  { label: 'Delivery', filters: { status: 'Project Delivery' } },
  { label: 'Critical', filters: { priority: 'critical' } },
  { label: 'FY69', filters: { fiscalYear: '69' } },
]

const activeFilters = computed(() => {
  const items = []
  if (store.filters.q) items.push(['q', `Search: ${store.filters.q}`])
  if (store.filters.status) items.push(['status', store.filters.status])
  if (store.filters.domain) items.push(['domain', store.filters.domain])
  if (store.filters.priority) {
    const label = PRIORITIES.find(([v]) => v === store.filters.priority)?.[1] || store.filters.priority
    items.push(['priority', label])
  }
  if (store.filters.fiscalYear) {
    const label = FYS.find(([v]) => v === store.filters.fiscalYear)?.[1] || store.filters.fiscalYear
    items.push(['fiscalYear', label])
  }
  return items
})

watch(
  () => store.filters.q,
  (value) => {
    if (value !== q.value) q.value = value || ''
  }
)

let timer
function onSearch(value) {
  q.value = value
  clearTimeout(timer)
  timer = setTimeout(() => store.setFilter({ q: value.trim() }), 250)
}

function applyView(view) {
  const base = view.label === 'All'
    ? view.filters
    : { q: '', status: '', domain: '', priority: '', fiscalYear: '', ...view.filters }
  store.setFilter(base)
}

function clearOne(key) {
  store.setFilter({ [key]: '' })
}
</script>

<template>
  <section class="filters" :class="{ compact }" aria-label="Project filters">
    <div class="search-box">
      <AppIcon name="search" :size="16" />
      <input
        :value="q"
        type="search"
        placeholder="Search projects, customers, PMs..."
        @input="onSearch($event.target.value)"
      />
    </div>

    <div class="saved" aria-label="Saved views">
      <button
        v-for="view in savedViews"
        :key="view.label"
        type="button"
        class="view-chip"
        @click="applyView(view)"
      >
        {{ view.label }}
      </button>
    </div>

    <div class="selects">
      <label>
        <span>Status</span>
        <select :value="store.filters.status" @change="store.setFilter({ status: $event.target.value })">
          <option value="">Any status</option>
          <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label>
        <span>Domain</span>
        <select :value="store.filters.domain" @change="store.setFilter({ domain: $event.target.value })">
          <option value="">Any domain</option>
          <option v-for="d in DOMAINS" :key="d" :value="d">{{ d }}</option>
        </select>
      </label>
      <label>
        <span>Priority</span>
        <select :value="store.filters.priority" @change="store.setFilter({ priority: $event.target.value })">
          <option value="">Any priority</option>
          <option v-for="[value, label] in PRIORITIES" :key="value" :value="value">{{ label }}</option>
        </select>
      </label>
      <label>
        <span>Fiscal year</span>
        <select :value="store.filters.fiscalYear" @change="store.setFilter({ fiscalYear: $event.target.value })">
          <option value="">Any FY</option>
          <option v-for="[value, label] in FYS" :key="value" :value="value">{{ label }}</option>
        </select>
      </label>
    </div>

    <div v-if="activeFilters.length" class="active">
      <span class="active-label"><AppIcon name="filter" :size="14" /> Active</span>
      <button v-for="[key, label] in activeFilters" :key="key" type="button" class="active-chip" @click="clearOne(key)">
        {{ label }}
        <AppIcon name="close" :size="12" />
      </button>
      <button type="button" class="clear" @click="store.clearFilters">Clear all</button>
    </div>
  </section>
</template>

<style scoped>
.filters {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}
.filters.compact {
  margin-bottom: 12px;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 9px;
  width: min(100%, 480px);
  padding: 0 12px;
  min-height: 40px;
  color: var(--text-dim);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.search-box input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 13px;
}
.saved,
.selects,
.active {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.view-chip,
.active-chip,
.clear {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  min-height: 30px;
  padding: 5px 10px;
  border-radius: 8px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.view-chip:hover,
.clear:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.selects label {
  display: grid;
  gap: 4px;
}
.selects span {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-dim);
}
.selects select {
  min-width: 132px;
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0 10px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 12px;
}
.active {
  padding-top: 2px;
}
.active-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 700;
}
.active-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
}
.clear {
  color: var(--text-dim);
}
@media (min-width: 1100px) {
  .filters:not(.compact) {
    grid-template-columns: minmax(280px, 420px) 1fr;
    align-items: start;
  }
  .filters:not(.compact) .selects,
  .filters:not(.compact) .active {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .filters { gap: 8px; margin-bottom: 12px; }
  .search-box { width: 100%; min-height: 38px; }
  .saved {
    overflow-x: auto;
    flex-wrap: nowrap;
    margin: 0 -14px;
    padding: 2px 14px;
    scroll-snap-type: x mandatory;
  }
  .saved::-webkit-scrollbar { display: none; }
  .view-chip { flex-shrink: 0; scroll-snap-align: start; }
  .selects {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .selects label { gap: 3px; }
  .selects select { min-width: 0; width: 100%; height: 36px; font-size: 13px; }
  .active { gap: 6px; }
  .active-chip { font-size: 11px; padding: 4px 8px; min-height: 26px; }
}
</style>

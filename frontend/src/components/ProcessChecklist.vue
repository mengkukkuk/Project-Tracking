<script setup>
import { computed, ref, watch } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'

const store = useProjectsStore()
const ui = useUiStore()

const rows = computed(() => store.records['ptrack'] || [])

const groups = computed(() => {
  const map = new Map()
  for (const r of rows.value) {
    const key = r.process || 'Ungrouped'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }
  return [...map.entries()].map(([process, items]) => ({
    process,
    items,
    done: items.filter((i) => i.checked).length,
  }))
})

const busy = ref(false)

watch(
  () => store.current,
  (cur) => {
    if (cur && !('ptrack' in store.records)) store.fetchRecords('ptrack')
  },
  { immediate: true },
)

async function toggle(rec) {
  try {
    await store.toggleProcess(rec)
  } catch (e) {
    ui.error(e.message)
  }
}

async function generate() {
  busy.value = true
  try {
    await store.generateProcess(store.current.id)
  } catch (e) {
    ui.error(e.message)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="panel proc">
    <div v-if="store.recordsLoading && !rows.length" class="empty">Loading...</div>

    <template v-else-if="rows.length">
      <div v-for="g in groups" :key="g.process" class="proc-group">
        <h3 class="sec-title">
          {{ g.process }} <span>{{ g.done }}/{{ g.items.length }}</span>
        </h3>
        <ul class="tasks">
          <li v-for="r in g.items" :key="r.id">
            <label>
              <input type="checkbox" :checked="r.checked" @change="toggle(r)" />
              <span :class="{ done: r.checked }">{{ r.task }}</span>
            </label>
          </li>
        </ul>
      </div>
    </template>

    <div v-else class="empty-state">
      <p class="empty">No process checklist yet for this project.</p>
      <button class="btn sm" :disabled="busy" @click="generate">
        {{ busy ? 'Generating...' : 'Generate from template' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.proc { display: grid; gap: 16px; font-family: var(--font); }
.proc-group { display: grid; gap: 8px; }
.sec-title {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.sec-title span { color: var(--text-dim); }
.tasks { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.tasks li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tasks label { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
.tasks input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); }
.tasks .done { text-decoration: line-through; color: var(--text-dim); }
.empty-state { display: grid; gap: 12px; justify-items: start; }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; }
</style>

<script setup>
import { computed, ref, watch } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'

const store = useProjectsStore()
const ui = useUiStore()
const { date, daysUntil } = useFormat()

const rows = computed(() => store.records['ptrack'] || [])

function addDays(iso, days) {
  if (!iso || days == null) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  d.setDate(d.getDate() + Number(days))
  return d.toISOString().slice(0, 10)
}

const groups = computed(() => {
  const map = new Map()
  for (const r of rows.value) {
    const key = r.process || 'Ungrouped'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }
  const projectStart = store.current?.startDate || null

  // Build group list and order it by the canonical cumulative offset so the
  // due-date chain runs through the processes in the right sequence.
  const list = [...map.entries()].map(([process, items]) => {
    const sample = items.find((i) => i.cumulativeDays != null) || items[0] || {}
    return {
      process,
      items,
      done: items.filter((i) => i.checked).length,
      dayRange: sample.dayRange ?? null,
      cumulativeDays: sample.cumulativeDays ?? null,
    }
  })
  list.sort((a, b) => {
    if (a.cumulativeDays == null) return 1
    if (b.cumulativeDays == null) return -1
    return a.cumulativeDays - b.cumulativeDays
  })

  // Chain:
  //   first process:   start = projectStart,         due = start + dayRange
  //   subsequent:      start = prevDue + 1 day,      due = start + dayRange
  let prevDue = null
  for (const g of list) {
    g.startDate = prevDue ? addDays(prevDue, 1) : projectStart
    g.dueDate = addDays(g.startDate, g.dayRange)
    g.remaining = daysUntil(g.dueDate)
    if (g.dueDate) prevDue = g.dueDate
  }
  return list
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
          <span class="proc-name">{{ g.process }}</span>
          <span
            v-if="g.dueDate"
            class="proc-due"
            :class="{
              overdue: g.remaining != null && g.remaining < 0,
              soon: g.remaining != null && g.remaining >= 0 && g.remaining <= 7,
            }"
          >
            <span v-if="g.startDate" class="due-date start">{{ date(g.startDate) }}</span>
            <span v-if="g.startDate" class="due-arrow" aria-hidden="true">→</span>
            <span class="due-date">{{ date(g.dueDate) }}</span>
            <span class="due-sep">·</span>
            <span class="due-rem">
              <template v-if="g.remaining == null">—</template>
              <template v-else-if="g.remaining < 0">
                Overdue {{ -g.remaining }} day{{ -g.remaining === 1 ? '' : 's' }}
              </template>
              <template v-else-if="g.remaining === 0">Due today</template>
              <template v-else>
                Remaining {{ g.remaining }} day{{ g.remaining === 1 ? '' : 's' }}
              </template>
            </span>
          </span>
          <span class="proc-count">{{ g.done }}/{{ g.items.length }}</span>
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
  align-items: baseline;
  gap: 12px;
  font-size: 12px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.sec-title .proc-name { color: var(--text); flex-shrink: 0; }
.sec-title .proc-count { color: var(--text-dim); margin-left: auto; }
.proc-due {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .03em;
  text-transform: none;
  color: var(--text-dim);
  background: color-mix(in srgb, var(--text-dim) 6%, transparent);
  white-space: nowrap;
}
.proc-due .due-date {
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.proc-due .due-sep { color: var(--border); }
.proc-due .due-arrow { color: var(--text-dim); font-weight: 500; }
.proc-due .due-date.start { color: var(--text-dim); }
.proc-due .due-rem { font-variant-numeric: tabular-nums; }
.proc-due.soon {
  color: var(--warning);
  border-color: color-mix(in srgb, var(--warning) 40%, var(--border));
  background: color-mix(in srgb, var(--warning) 10%, transparent);
}
.proc-due.soon .due-date { color: var(--warning); }
.proc-due.overdue {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 50%, var(--border));
  background: color-mix(in srgb, var(--danger) 12%, transparent);
}
.proc-due.overdue .due-date { color: var(--danger); }
.tasks { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.tasks li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tasks label { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
.tasks input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); }
.tasks .done { text-decoration: line-through; color: var(--text-dim); }
.empty-state { display: grid; gap: 12px; justify-items: start; }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; }
</style>

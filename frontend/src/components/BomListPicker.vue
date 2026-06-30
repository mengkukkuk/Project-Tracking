<script setup>
// Pick BOM rows for a saved list — used in both create and edit modes.
// Reuses the global BOM store as the source pool (no extra fetch). Selection
// state is local: a Set<bom_id>. Save persists to the bom-lists endpoint;
// Save & Export downloads after a successful save.
import { ref, computed, onMounted, watch } from 'vue'
import { useBomStore } from '@/stores/bom'
import { useBomListsStore } from '@/stores/bomLists'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { exportBomListExcel, exportBomListPdf } from '@/utils/recordExport'
import Modal from './Modal.vue'

const props = defineProps({
  // `null` when creating, a list summary object (with id) when editing.
  list: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const bomStore = useBomStore()
const listsStore = useBomListsStore()
const projectsStore = useProjectsStore()
const ui = useUiStore()

const isEdit = computed(() => !!props.list?.id)
const title = computed(() =>
  isEdit.value ? `Edit BOM List — ${form.value.name || ''}` : 'Create BOM List',
)

const form = ref({
  name: props.list?.name || '',
  projectId: props.list?.projectId ?? null,
})
const selectedIds = ref(new Set())
const sourceProjectFilter = ref('') // optional dropdown
const q = ref('')
const showSelectedOnly = ref(false)
const saving = ref(false)

const projectOptions = computed(() =>
  [...projectsStore.projects].sort((a, b) =>
    (a.name || '').localeCompare(b.name || ''),
  ),
)

// Pool of candidate rows. We use the bom store rows directly — same data the
// /bom page already showed the user.
const pool = computed(() => bomStore.rows || [])

const filtered = computed(() => {
  const term = q.value.trim().toLowerCase()
  const pf = sourceProjectFilter.value
  return pool.value.filter((r) => {
    if (pf && r.projectId !== Number(pf)) return false
    if (showSelectedOnly.value && !selectedIds.value.has(r.id)) return false
    if (!term) return true
    return ['deviceName', 'spec', 'category', 'supplier', 'projectName'].some(
      (k) => String(r[k] || '').toLowerCase().includes(term),
    )
  })
})

const selectedCount = computed(() => selectedIds.value.size)
const filteredAllSelected = computed(
  () =>
    filtered.value.length > 0 &&
    filtered.value.every((r) => selectedIds.value.has(r.id)),
)
const invalid = computed(
  () => !form.value.name.trim() || !form.value.projectId || selectedCount.value === 0,
)
const targetProject = computed(
  () => projectsStore.projects.find((p) => p.id === Number(form.value.projectId)) || null,
)

function toggle(id) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}
function toggleAllVisible() {
  const s = new Set(selectedIds.value)
  if (filteredAllSelected.value) {
    for (const r of filtered.value) s.delete(r.id)
  } else {
    for (const r of filtered.value) s.add(r.id)
  }
  selectedIds.value = s
}

function num(v) {
  return v == null || v === '' ? '—' : Number(v).toLocaleString()
}

// On edit mode: seed selection from the detail endpoint (the list summary
// passed in doesn't carry items[], so fetch detail once).
onMounted(async () => {
  if (!bomStore.rows.length) {
    try {
      await bomStore.fetchAll()
    } catch (e) {
      ui.error(e.message)
    }
  }
  if (!projectsStore.projects.length) {
    try {
      await projectsStore.fetchAll()
    } catch (e) {
      /* surface elsewhere */
    }
  }
  if (isEdit.value) {
    try {
      const detail = await listsStore.fetchOne(props.list.id)
      form.value.name = detail.name
      form.value.projectId = detail.projectId
      selectedIds.value = new Set((detail.items || []).map((it) => it.id))
    } catch (e) {
      ui.error(e.message)
    }
  }
})

// Build the rows actually saved/exported (in the order they appear in the pool
// so the user sees the same order as the table they picked from).
function selectedRows() {
  const idsInOrder = pool.value.filter((r) => selectedIds.value.has(r.id))
  return idsInOrder
}

async function save({ thenExport } = {}) {
  if (invalid.value) return
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      projectId: Number(form.value.projectId),
      itemIds: [...selectedIds.value],
    }
    if (isEdit.value) await listsStore.update(props.list.id, payload)
    else await listsStore.create(payload)
    ui.success(isEdit.value ? 'BOM list updated' : 'BOM list created')

    if (thenExport) {
      const rows = selectedRows()
      const project = targetProject.value
      try {
        if (thenExport === 'excel') await exportBomListExcel(project, payload.name, rows)
        else exportBomListPdf(project, payload.name, rows)
        ui.success(`Exported to ${thenExport === 'excel' ? 'Excel' : 'PDF'}`)
      } catch (e) {
        ui.error(e.message)
      }
    }
    emit('saved')
  } catch (e) {
    ui.error(e.message)
  } finally {
    saving.value = false
  }
}

// Watch projectId to clear selection if the user clears it (no real reason to
// clear; we keep selections so the user can change target project mid-build).
watch(() => form.value.projectId, () => {})
</script>

<template>
  <Modal :title="title" wide @close="emit('close')">
    <div class="picker">
      <!-- Header form: name + target project + filters --------------------- -->
      <div class="grid">
        <label class="field">
          <span>List name<em class="req">*</em></span>
          <input v-model="form.name" class="input" placeholder="e.g. Procurement Q3" />
        </label>
        <label class="field">
          <span>Target project<em class="req">*</em></span>
          <select v-model="form.projectId" class="input">
            <option :value="null" disabled>Select a project…</option>
            <option v-for="p in projectOptions" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>

        <label class="field">
          <span>Filter by source project</span>
          <select v-model="sourceProjectFilter" class="input">
            <option value="">— all projects —</option>
            <option v-for="p in projectOptions" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>Search</span>
          <input v-model="q" class="input" type="search" placeholder="device, spec, supplier…" />
        </label>
      </div>

      <div class="toolbar">
        <label class="check">
          <input v-model="showSelectedOnly" type="checkbox" />
          <span>Show selected only</span>
        </label>
        <span class="count">
          <strong>{{ selectedCount }}</strong> selected
          <span class="of">of {{ filtered.length }} visible</span>
        </span>
      </div>

      <!-- Pickable table --------------------------------------------------- -->
      <div class="ledger">
        <table>
          <thead>
            <tr>
              <th class="check-col">
                <input
                  type="checkbox"
                  :checked="filteredAllSelected"
                  :disabled="!filtered.length"
                  @change="toggleAllVisible"
                />
              </th>
              <th>Project</th>
              <th>Device</th>
              <th>Category</th>
              <th class="num">Qty</th>
              <th class="num">Unit price</th>
              <th class="num">Total price</th>
              <th>Supplier</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in filtered"
              :key="r.id"
              class="row"
              :class="{ on: selectedIds.has(r.id) }"
              @click="toggle(r.id)"
            >
              <td class="check-col" @click.stop>
                <input type="checkbox" :checked="selectedIds.has(r.id)" @change="toggle(r.id)" />
              </td>
              <td class="proj">{{ r.projectName || '—' }}</td>
              <td>{{ r.deviceName || '—' }}</td>
              <td>{{ r.category || '—' }}</td>
              <td class="num">{{ num(r.quantity) }}</td>
              <td class="num">{{ num(r.unitPrice) }}</td>
              <td class="num">{{ num(r.totalPrice) }}</td>
              <td>{{ r.supplier || '—' }}</td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="8" class="empty">
                <span class="empty-mark">—</span>
                No rows match the current filter.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template #footer>
      <button type="button" class="btn ghost" @click="emit('close')">Cancel</button>
      <button
        type="button"
        class="btn ghost"
        :disabled="saving || invalid"
        @click="save({ thenExport: 'excel' })"
      >
        Save & Export Excel
      </button>
      <button
        type="button"
        class="btn ghost"
        :disabled="saving || invalid"
        @click="save({ thenExport: 'pdf' })"
      >
        Save & Export PDF
      </button>
      <button
        type="button"
        class="btn"
        :disabled="saving || invalid"
        @click="save()"
      >
        {{ saving ? 'Saving…' : isEdit ? 'Save changes' : 'Save' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.picker { display: grid; gap: 14px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: grid; gap: 5px; }
.field > span {
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .05em;
  text-transform: uppercase;
}
.req { color: var(--accent); font-style: normal; margin-left: 2px; }
select.input { appearance: auto; }

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 2px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.check { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; color: var(--text-dim); }
.check input { width: 14px; height: 14px; accent-color: var(--accent); }
.count { font-size: 12px; color: var(--text-dim); font-variant-numeric: tabular-nums; }
.count strong { color: var(--accent); font-weight: 700; }
.count .of { color: color-mix(in srgb, var(--text-dim) 70%, transparent); margin-left: 4px; }

.ledger { max-height: 50vh; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
table { width: 100%; border-collapse: collapse; }
thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface);
  text-align: left;
  padding: 8px 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th.num, td.num { text-align: right; }
.check-col { width: 28px; text-align: center; padding: 0 6px !important; }
.check-col input { width: 14px; height: 14px; accent-color: var(--accent); cursor: pointer; }

tbody td {
  padding: 8px 10px;
  font-size: 12.5px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
td.num { font-variant-numeric: tabular-nums; font-weight: 600; }
td.proj { font-weight: 600; }
.row { cursor: pointer; transition: background .1s; }
.row:hover { background: color-mix(in srgb, var(--accent) 6%, var(--surface)); }
.row.on { background: color-mix(in srgb, var(--accent) 11%, var(--surface)); }
tbody tr:last-child td { border-bottom: none; }

.empty { text-align: center; padding: 32px; color: var(--text-dim); font-style: italic; }
.empty-mark { display: block; font-size: 20px; color: var(--border); margin-bottom: 4px; }

@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
  .ledger { max-height: 60vh; }
}
</style>

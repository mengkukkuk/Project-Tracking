<script setup>
// Pick BOM rows for a saved list — used in both create and edit modes.
// Reuses the global BOM store as the source pool (no extra fetch). Selection
// state is local: a Set<bom_id>. Save persists to the bom-lists endpoint;
// Save & Export downloads after a successful save.
import { ref, computed, onMounted, watch, nextTick } from 'vue'
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
const categoryFilter = ref('')
const positionFilter = ref('')
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

// Distinct category/position values from the pool back the two dropdown
// filters (mirrors BomGlobalView's categoryOptions).
const categoryOptions = computed(() =>
  [...new Set(pool.value.map((r) => r.category).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  ),
)
const positionOptions = computed(() =>
  [...new Set(pool.value.map((r) => r.position).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  ),
)

const filtered = computed(() => {
  const term = q.value.trim().toLowerCase()
  const pf = sourceProjectFilter.value
  const cat = categoryFilter.value
  const pos = positionFilter.value
  return pool.value.filter((r) => {
    if (pf && r.projectId !== Number(pf)) return false
    if (cat && r.category !== cat) return false
    if (pos && r.position !== pos) return false
    if (showSelectedOnly.value && !selectedIds.value.has(r.id)) return false
    if (!term) return true
    return ['deviceName', 'spec', 'category', 'supplier', 'projectName'].some(
      (k) => String(r[k] || '').toLowerCase().includes(term),
    )
  })
})

// --- Column sorting ---------------------------------------------------------
// Click a header to sort by that field; click again to flip direction. Numeric
// columns compare as numbers, the rest case-insensitively as strings. Blanks
// always sink to the bottom regardless of direction.
const NUMERIC_KEYS = new Set(['quantity', 'unitPrice', 'totalPrice'])
const sortKey = ref('')
const sortDir = ref('asc')

function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const sorted = computed(() => {
  const key = sortKey.value
  if (!key) return filtered.value
  const dir = sortDir.value === 'desc' ? -1 : 1
  const numeric = NUMERIC_KEYS.has(key)
  const blank = (v) => v == null || v === ''
  return [...filtered.value].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (blank(av) && blank(bv)) return 0
    if (blank(av)) return 1
    if (blank(bv)) return -1
    const cmp = numeric
      ? Number(av) - Number(bv)
      : String(av).localeCompare(String(bv), undefined, { numeric: true })
    return cmp * dir
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

// --- Column resizing --------------------------------------------------------
// CSS `resize` doesn't apply to table cells, so widths are driven by a
// <colgroup> plus drag grips. Columns start in auto layout (so they size to
// content and full device names show); on the first drag we snapshot those
// widths and switch to fixed layout so columns can then grow AND shrink.
const COL_COUNT = 10 // checkbox + 9 data columns
// The Device column (colWidths index 2 → colgroup <col> #3) renders at a wider
// 350px default so full device names show, and never resizes below 200px.
const DEVICE_COL = 2
const DEVICE_DEFAULT = 350
const COL_MIN = { [DEVICE_COL]: 200 }
const tableEl = ref(null)
const colWidths = ref([])
const layoutFixed = ref(false)

// colgroup width for each <col> (1-based index i). Before the first drag we're
// in auto layout, but Device still gets its 350px default as a soft minimum.
function colStyle(i) {
  const idx = i - 1
  if (layoutFixed.value && colWidths.value[idx]) {
    return { width: colWidths.value[idx] + 'px' }
  }
  if (idx === DEVICE_COL) return { width: DEVICE_DEFAULT + 'px' }
  return null
}

// Snapshot the content-sized header widths into colWidths and lock to fixed
// layout, but pin Device to its 350px default. Runs once as soon as rows exist
// so Device opens at 350px (not ballooned to its longest name) while the other
// columns keep their natural first-render widths. Both are then resizable.
function seedWidths() {
  const table = tableEl.value
  if (!table || layoutFixed.value) return
  const ths = table.querySelectorAll('thead th')
  const w = [...ths].map((th) => th.getBoundingClientRect().width)
  if (!w.length || !w.some((x) => x > 0)) return
  w[DEVICE_COL] = DEVICE_DEFAULT
  colWidths.value = w
  layoutFixed.value = true
}

function startResize(index, e) {
  const table = tableEl.value
  if (!table) return
  if (!layoutFixed.value) {
    const ths = table.querySelectorAll('thead th')
    colWidths.value = [...ths].map((th) => th.getBoundingClientRect().width)
    layoutFixed.value = true
  }
  const startX = e.clientX
  const startW = colWidths.value[index]
  const min = COL_MIN[index] ?? 48
  const onMove = (ev) => {
    const next = [...colWidths.value]
    next[index] = Math.max(min, startW + (ev.clientX - startX))
    colWidths.value = next
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
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

// Seed column widths once the first rows have rendered (Device → 350px default).
watch(
  () => filtered.value.length,
  async (n) => {
    if (n && !layoutFixed.value) {
      await nextTick()
      seedWidths()
    }
  },
  { immediate: true },
)
</script>

<template>
  <Modal :title="title" xwide @close="emit('close')">
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
          <span>Category</span>
          <select v-model="categoryFilter" class="input">
            <option value="">— any category —</option>
            <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label class="field">
          <span>Position</span>
          <select v-model="positionFilter" class="input">
            <option value="">— any position —</option>
            <option v-for="pos in positionOptions" :key="pos" :value="pos">{{ pos }}</option>
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
        <table ref="tableEl" :style="{ tableLayout: layoutFixed ? 'fixed' : 'auto' }">
          <colgroup>
            <col
              v-for="i in COL_COUNT"
              :key="i"
              :style="colStyle(i)"
            />
          </colgroup>
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
              <th :aria-sort="sortKey === 'projectName' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('projectName')">
                  Project<span class="sort-ind" :class="{ on: sortKey === 'projectName' }">{{ sortKey === 'projectName' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(1, $event)" />
              </th>
              <th :aria-sort="sortKey === 'deviceName' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('deviceName')">
                  Device<span class="sort-ind" :class="{ on: sortKey === 'deviceName' }">{{ sortKey === 'deviceName' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(2, $event)" />
              </th>
              <th :aria-sort="sortKey === 'version' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('version')">
                  Version<span class="sort-ind" :class="{ on: sortKey === 'version' }">{{ sortKey === 'version' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(3, $event)" />
              </th>
              <th :aria-sort="sortKey === 'category' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('category')">
                  Category<span class="sort-ind" :class="{ on: sortKey === 'category' }">{{ sortKey === 'category' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(4, $event)" />
              </th>
              <th :aria-sort="sortKey === 'position' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('position')">
                  Position<span class="sort-ind" :class="{ on: sortKey === 'position' }">{{ sortKey === 'position' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(5, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'quantity' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('quantity')">
                  <span class="sort-ind" :class="{ on: sortKey === 'quantity' }">{{ sortKey === 'quantity' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Qty
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(6, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'unitPrice' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('unitPrice')">
                  <span class="sort-ind" :class="{ on: sortKey === 'unitPrice' }">{{ sortKey === 'unitPrice' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Unit price
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(7, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'totalPrice' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('totalPrice')">
                  <span class="sort-ind" :class="{ on: sortKey === 'totalPrice' }">{{ sortKey === 'totalPrice' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Total price
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(8, $event)" />
              </th>
              <th :aria-sort="sortKey === 'supplier' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('supplier')">
                  Supplier<span class="sort-ind" :class="{ on: sortKey === 'supplier' }">{{ sortKey === 'supplier' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(9, $event)" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in sorted"
              :key="r.id"
              class="row"
              :class="{ on: selectedIds.has(r.id) }"
              @click="toggle(r.id)"
            >
              <td class="check-col" @click.stop>
                <input type="checkbox" :checked="selectedIds.has(r.id)" @change="toggle(r.id)" />
              </td>
              <td class="proj">{{ r.projectName || '—' }}</td>
              <td class="device">{{ r.deviceName || '—' }}</td>
              <td>{{ r.version || '—' }}</td>
              <td>{{ r.category || '—' }}</td>
              <td>{{ r.position || '—' }}</td>
              <td class="num">{{ num(r.quantity) }}</td>
              <td class="num">{{ num(r.unitPrice) }}</td>
              <td class="num">{{ num(r.totalPrice) }}</td>
              <td>{{ r.supplier || '—' }}</td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="10" class="empty">
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
/* auto layout lets columns size to their content first (full device names show
   when the xwide modal has room); the drag grips then switch to fixed layout. */
table { width: 100%; border-collapse: collapse; table-layout: auto; }
thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface);
  text-align: left;
  padding: 0 14px 0 0;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  overflow: hidden;
  min-width: 48px;
}
/* The header label is a button so the whole cell is a keyboard-reachable sort
   control; it carries the type styling the <th> used to have. */
.sort-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  background: none;
  font: inherit;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-dim);
  cursor: pointer;
}
th.num .sort-label { justify-content: flex-end; }
.sort-label:hover { color: var(--text); }
.sort-label:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.sort-ind {
  font-size: 11px;
  line-height: 1;
  opacity: .4;
  transition: opacity .1s, color .1s;
}
.sort-ind.on { opacity: 1; color: var(--accent); }
/* Drag grip on the right edge of each header; sets that column's width. */
.col-grip {
  position: absolute;
  top: 0; right: 0;
  width: 9px; height: 100%;
  cursor: col-resize;
  user-select: none;
  touch-action: none;
}
.col-grip::after {
  content: '';
  position: absolute;
  top: 25%; bottom: 25%; right: 3px;
  border-right: 2px solid var(--border);
}
.col-grip:hover::after { border-color: var(--accent); }
th.check-col { min-width: 0; }
th.num, td.num { text-align: right; }
.check-col { width: 28px; text-align: center; padding: 0 6px !important; }
.check-col input { width: 14px; height: 14px; accent-color: var(--accent); cursor: pointer; }

tbody td {
  padding: 8px 10px;
  font-size: 12.5px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

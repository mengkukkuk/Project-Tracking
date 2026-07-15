<script setup>
// Pick catalogue entries (+ a quantity each) for a saved list — used in both
// create and edit modes. The pool is the read-only inventory catalogue.
// Selection state is local: a Map<inventoryId, quantity>. Save persists to the
// bom-lists endpoint; Save & Export downloads after a successful save.
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useInventoryStore } from '@/stores/inventory'
import { useBomListsStore } from '@/stores/bomLists'
import { useProjectsStore } from '@/stores/projects'
import { useLookupsStore } from '@/stores/lookups'
import { useUiStore } from '@/stores/ui'
import { exportBomListExcel } from '@/utils/recordExport'
import Modal from './Modal.vue'

const props = defineProps({
  // `null` when creating, a list summary object (with id) when editing.
  list: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved', 'request-pdf-export'])

const inventoryStore = useInventoryStore()
const listsStore = useBomListsStore()
const projectsStore = useProjectsStore()
const lookupsStore = useLookupsStore()
const ui = useUiStore()

const isEdit = computed(() => !!props.list?.id)
const title = computed(() =>
  isEdit.value ? `Edit BOM List — ${form.value.name || ''}` : 'Create BOM List',
)

const form = ref({
  name: props.list?.name || '',
  projectId: props.list?.projectId ?? null,
})
// Map<inventoryId, quantity>. Replaced (never mutated) so computeds re-run.
const selected = ref(new Map())
const categoryFilter = ref('') // taxonomy code
const typeFilter = ref('') // taxonomy code, cascades off categoryFilter
const q = ref('')
const showSelectedOnly = ref(false)
const saving = ref(false)

const projectOptions = computed(() =>
  [...projectsStore.projects].sort((a, b) =>
    (a.name || '').localeCompare(b.name || ''),
  ),
)

// Pool of candidate rows: the inventory catalogue. Entries are project-
// independent, so there is no source-project filter here.
const pool = computed(() => inventoryStore.rows || [])

// Category/Type options come from the lookup_type/lookup_value taxonomy
// (lookupsStore), mirroring BomGlobalView so the picker offers the same
// taxonomy-backed choices.
const categoryOptions = computed(() => lookupsStore.types)
const typeOptions = computed(
  () => lookupsStore.typeByCode(categoryFilter.value)?.values || [],
)

// Type is meaningless without a Category, so clearing/changing Category also
// clears any previously-chosen Type (mirrors BomGlobalView's onCategoryChange).
watch(categoryFilter, () => {
  typeFilter.value = ''
})

// Catalogue entries carry the taxonomy as real FK ids and have no free-text
// `category` column, so matching is a direct id compare — none of the
// free-text fallbacks BomGlobalView needs for legacy/imported BOM rows.
// Unclassified entries (categoryId === null) simply never match a filter.
const filtered = computed(() => {
  const term = q.value.trim().toLowerCase()
  const cat = categoryFilter.value
  const typ = typeFilter.value

  const selType = cat ? lookupsStore.typeByCode(cat) : null
  const selValue = selType && typ ? selType.values?.find((v) => v.code === typ) : null

  return pool.value.filter((r) => {
    if (cat && !(selType && r.categoryId === selType.id)) return false
    if (typ && !(selValue && r.typeId === selValue.id)) return false
    if (showSelectedOnly.value && !selected.value.has(r.id)) return false
    if (!term) return true
    return ['deviceName', 'spec', 'category', 'type', 'supplier'].some((k) =>
      String(r[k] || '').toLowerCase().includes(term),
    )
  })
})

// --- Quantity + derived total -----------------------------------------------
// Quantity lives in the selection, not on the catalogue entry, so an unticked
// row has none. Total mirrors the server's rule: qty x unitPrice, and no total
// at all when the entry is unpriced (rather than a misleading zero).
function qtyOf(r) {
  return selected.value.get(r.id) ?? null
}
function totalOf(r) {
  const qty = qtyOf(r)
  return qty == null || r.unitPrice == null ? null : qty * r.unitPrice
}

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

// Qty/Total aren't row properties — they're derived from the selection.
function sortValue(row, key) {
  if (key === 'quantity') return qtyOf(row)
  if (key === 'totalPrice') return totalOf(row)
  return row[key]
}

const sorted = computed(() => {
  const key = sortKey.value
  if (!key) return filtered.value
  const dir = sortDir.value === 'desc' ? -1 : 1
  const numeric = NUMERIC_KEYS.has(key)
  const blank = (v) => v == null || v === ''
  return [...filtered.value].sort((a, b) => {
    const av = sortValue(a, key)
    const bv = sortValue(b, key)
    if (blank(av) && blank(bv)) return 0
    if (blank(av)) return 1
    if (blank(bv)) return -1
    const cmp = numeric
      ? Number(av) - Number(bv)
      : String(av).localeCompare(String(bv), undefined, { numeric: true })
    return cmp * dir
  })
})

const selectedCount = computed(() => selected.value.size)
const filteredAllSelected = computed(
  () =>
    filtered.value.length > 0 &&
    filtered.value.every((r) => selected.value.has(r.id)),
)
const invalid = computed(
  () => !form.value.name.trim() || !form.value.projectId || selectedCount.value === 0,
)
const targetProject = computed(
  () => projectsStore.projects.find((p) => p.id === Number(form.value.projectId)) || null,
)

// Ticking a row defaults it to qty 1; untickng forgets the quantity. Re-ticking
// therefore starts at 1 again rather than resurrecting a stale value.
function toggle(id) {
  const m = new Map(selected.value)
  if (m.has(id)) m.delete(id)
  else m.set(id, 1)
  selected.value = m
}
function toggleAllVisible() {
  const m = new Map(selected.value)
  if (filteredAllSelected.value) {
    for (const r of filtered.value) m.delete(r.id)
  } else {
    // Keep any quantity already set; only newly-added rows default to 1.
    for (const r of filtered.value) if (!m.has(r.id)) m.set(r.id, 1)
  }
  selected.value = m
}

// The server rejects qty < 1, so clamp here rather than let the user build a
// payload that 422s on save. A blank/NaN input falls back to 1.
function setQty(id, raw) {
  const n = Math.max(1, Math.floor(Number(raw) || 1))
  const m = new Map(selected.value)
  m.set(id, n)
  selected.value = m
}

function num(v) {
  return v == null || v === '' ? '—' : Number(v).toLocaleString()
}

// --- Column resizing --------------------------------------------------------
// CSS `resize` doesn't apply to table cells, so widths are driven by a
// <colgroup> plus drag grips. Columns start in auto layout (so they size to
// content and full device names show); on the first drag we snapshot those
// widths and switch to fixed layout so columns can then grow AND shrink.
const COL_COUNT = 9 // checkbox + 8 data columns
// The Device column (colWidths index 1 → colgroup <col> #2) renders at a wider
// 350px default so full device names show, and never resizes below 200px.
const DEVICE_COL = 1
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
  if (!inventoryStore.rows.length) {
    try {
      await inventoryStore.fetchAll()
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
  if (!lookupsStore.types.length) {
    try {
      await lookupsStore.fetchAll()
    } catch (e) {
      /* lookups are non-critical; filters just show no options */
    }
  }
  if (isEdit.value) {
    try {
      const detail = await listsStore.fetchOne(props.list.id)
      form.value.name = detail.name
      form.value.projectId = detail.projectId
      // Seed quantities from the saved list, NOT a default of 1. save() always
      // resends the full selection and the server clears-and-rebuilds, so
      // defaulting here would let a plain rename wipe every stored quantity.
      selected.value = new Map(
        (detail.items || []).map((it) => [it.id, it.quantity ?? 1]),
      )
    } catch (e) {
      ui.error(e.message)
    }
  }
})

// Build the rows actually saved/exported (in the order they appear in the pool
// so the user sees the same order as the table they picked from). Exports need
// the derived qty/total, which live in the selection rather than on the entry.
function selectedRows() {
  return pool.value
    .filter((r) => selected.value.has(r.id))
    .map((r) => ({ ...r, quantity: qtyOf(r), totalPrice: totalOf(r) }))
}

async function save({ thenExport } = {}) {
  if (invalid.value) return
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      projectId: Number(form.value.projectId),
      items: [...selected.value].map(([inventoryId, quantity]) => ({
        inventoryId,
        quantity,
      })),
    }
    if (isEdit.value) await listsStore.update(props.list.id, payload)
    else await listsStore.create(payload)
    ui.success(isEdit.value ? 'BOM list updated' : 'BOM list created')

    if (thenExport === 'excel') {
      try {
        await exportBomListExcel(targetProject.value, payload.name, selectedRows())
        ui.success('Exported to Excel')
      } catch (e) {
        ui.error(e.message)
      }
    } else if (thenExport === 'pdf') {
      // Hand off to the doc-picker modal (owned by BomGlobalView). Emit before
      // closing so the view can open the modal over itself, not over the picker.
      emit('request-pdf-export', {
        project: targetProject.value,
        listName: payload.name,
        rows: selectedRows(),
      })
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
      <!-- Left rail: name + target project + filters ------------------------ -->
      <div class="filters-col">
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
            <span>Category</span>
            <select v-model="categoryFilter" class="input">
              <option value="">— any category —</option>
              <option v-for="t in categoryOptions" :key="t.code" :value="t.code">
                {{ t.description || t.name }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>Type</span>
            <select v-model="typeFilter" class="input" :disabled="!categoryFilter">
              <option value="">— any type —</option>
              <option v-for="v in typeOptions" :key="v.code" :value="v.code">{{ v.displayName }}</option>
            </select>
          </label>
          <label class="field">
            <span>Search</span>
            <input v-model="q" class="input" type="search" placeholder="device, spec, supplier…" />
          </label>
        </div>
      </div>

      <!-- Right column: toolbar + pickable table ----------------------------- -->
      <div class="table-col">
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
              <th :aria-sort="sortKey === 'deviceName' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('deviceName')">
                  Device<span class="sort-ind" :class="{ on: sortKey === 'deviceName' }">{{ sortKey === 'deviceName' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(1, $event)" />
              </th>
              <th :aria-sort="sortKey === 'version' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('version')">
                  Version<span class="sort-ind" :class="{ on: sortKey === 'version' }">{{ sortKey === 'version' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(2, $event)" />
              </th>
              <th :aria-sort="sortKey === 'category' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('category')">
                  Category<span class="sort-ind" :class="{ on: sortKey === 'category' }">{{ sortKey === 'category' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(3, $event)" />
              </th>
              <th :aria-sort="sortKey === 'type' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('type')">
                  Type<span class="sort-ind" :class="{ on: sortKey === 'type' }">{{ sortKey === 'type' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(4, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'quantity' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('quantity')">
                  <span class="sort-ind" :class="{ on: sortKey === 'quantity' }">{{ sortKey === 'quantity' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Qty
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(5, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'unitPrice' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('unitPrice')">
                  <span class="sort-ind" :class="{ on: sortKey === 'unitPrice' }">{{ sortKey === 'unitPrice' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Unit price
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(6, $event)" />
              </th>
              <th class="num" :aria-sort="sortKey === 'totalPrice' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('totalPrice')">
                  <span class="sort-ind" :class="{ on: sortKey === 'totalPrice' }">{{ sortKey === 'totalPrice' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>Total price
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(7, $event)" />
              </th>
              <th :aria-sort="sortKey === 'supplier' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                <button type="button" class="sort-label" @click="sortBy('supplier')">
                  Supplier<span class="sort-ind" :class="{ on: sortKey === 'supplier' }">{{ sortKey === 'supplier' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
                </button>
                <span class="col-grip" @pointerdown.prevent.stop="startResize(8, $event)" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in sorted"
              :key="r.id"
              class="row"
              :class="{ on: selected.has(r.id) }"
              @click="toggle(r.id)"
            >
              <td class="check-col" @click.stop>
                <input type="checkbox" :checked="selected.has(r.id)" @change="toggle(r.id)" />
              </td>
              <td class="device">{{ r.deviceName || '—' }}</td>
              <td>{{ r.version || '—' }}</td>
              <td>{{ r.category || '—' }}</td>
              <td>{{ r.type || '—' }}</td>
              <!-- Qty is editable only once the row is picked; @click.stop keeps
                   typing in it from toggling the row off. -->
              <td class="num" @click.stop>
                <input
                  v-if="selected.has(r.id)"
                  class="qty"
                  type="number"
                  min="1"
                  step="1"
                  :value="qtyOf(r)"
                  :aria-label="`Quantity for ${r.deviceName || 'item'}`"
                  @input="setQty(r.id, $event.target.value)"
                />
                <span v-else>—</span>
              </td>
              <td class="num">{{ num(r.unitPrice) }}</td>
              <td class="num">{{ num(totalOf(r)) }}</td>
              <td>{{ r.supplier || '—' }}</td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="9" class="empty">
                <span class="empty-mark">—</span>
                No rows match the current filter.
              </td>
            </tr>
          </tbody>
        </table>
        </div>
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
/* Left rail (filters, 40%) / right column (table, 60%). Narrower left column
   means .input/.select (width:100% of their parent, see main.css) naturally
   shrink to fit instead of stretching across half the xwide modal. */
.picker {
  display: grid;
  grid-template-columns: 2fr 3fr;
  gap: 20px;
  align-items: start;
}
.filters-col { display: grid; gap: 14px; }
.table-col { display: grid; gap: 14px; }
.grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
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

.ledger { max-height: 60vh; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
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
/* Inline qty editor: sized to ~3 digits so it never widens the Qty column. */
.qty {
  width: 56px;
  padding: 3px 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  text-align: right;
  accent-color: var(--accent);
}
.qty:focus-visible { outline: 2px solid var(--accent); outline-offset: -1px; }
.row { cursor: pointer; transition: background .1s; }
.row:hover { background: color-mix(in srgb, var(--accent) 6%, var(--surface)); }
.row.on { background: color-mix(in srgb, var(--accent) 11%, var(--surface)); }
tbody tr:last-child td { border-bottom: none; }

.empty { text-align: center; padding: 32px; color: var(--text-dim); font-style: italic; }
.empty-mark { display: block; font-size: 20px; color: var(--border); margin-bottom: 4px; }

/* Collapse the left/right split back to a single stacked column before the
   modal itself goes full-bleed (Modal.vue's .xwide breakpoint is 800px). */
@media (max-width: 900px) {
  .picker { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .ledger { max-height: 60vh; }
}
</style>

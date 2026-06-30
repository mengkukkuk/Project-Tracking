<script setup>
import { ref, h, computed, onMounted } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  FlexRender,
} from '@tanstack/vue-table'
import { useBomStore } from '@/stores/bom'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import ExportImportMenu from '@/components/ExportImportMenu.vue'
import ImportResultModal from '@/components/ImportResultModal.vue'
import Modal from '@/components/Modal.vue'
import BomGlobalForm from '@/components/BomGlobalForm.vue'
import BomListPicker from '@/components/BomListPicker.vue'
import BomListsManager from '@/components/BomListsManager.vue'
import {
  exportBomInventoryExcel,
  exportBomInventoryPdf,
  parseBomInventoryExcel,
} from '@/utils/recordExport'
import { api } from '@/api'

const store = useBomStore()
const projectsStore = useProjectsStore()
const ui = useUiStore()
const { date } = useFormat()

const sorting = ref([{ id: 'projectName', desc: false }])

const today = new Date()
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  .toUpperCase()

const num = (v) => (v == null || v === '' ? '—' : Number(v).toLocaleString())

// Right-aligned figure columns.
const NUM_COLS = new Set(['quantity', 'unitPrice', 'totalPrice', 'leadTime'])

// Client-side text search across the most useful free-text fields.
const filtered = computed(() => {
  const q = store.q.trim().toLowerCase()
  if (!q) return store.rows
  return store.rows.filter((r) =>
    ['deviceName', 'spec', 'category', 'supplier', 'projectName'].some((k) =>
      String(r[k] || '').toLowerCase().includes(q),
    ),
  )
})

const columns = [
  {
    accessorKey: 'projectName',
    header: 'Project',
    cell: (i) => h('strong', { class: 'project-cell' }, i.getValue() || '—'),
  },
  { accessorKey: 'deviceName', header: 'Device name', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'category', header: 'Category', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'version', header: 'Version', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'quantity', header: 'Qty', cell: (i) => num(i.getValue()) },
  { accessorKey: 'unit', header: 'Unit', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'position', header: 'Position', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'unitPrice', header: 'Unit price', cell: (i) => num(i.getValue()) },
  { accessorKey: 'totalPrice', header: 'Total price', cell: (i) => num(i.getValue()) },
  { accessorKey: 'leadTime', header: 'Lead time', cell: (i) => num(i.getValue()) },
  { accessorKey: 'supplier', header: 'Supplier', cell: (i) => i.getValue() || '—' },
  { accessorKey: 'dateApprove', header: 'Approved on', cell: (i) => date(i.getValue()) },
  {
    id: 'actions',
    header: '',
    enableSorting: false,
    cell: (i) =>
      h('div', { class: 'row-actions' }, [
        h('button', { class: 'mini', onClick: () => openEdit(i.row.original) }, 'Edit'),
        h('button', { class: 'mini danger', onClick: () => remove(i.row.original) }, 'Delete'),
      ]),
  },
]

const table = useVueTable({
  get data() {
    return filtered.value
  },
  columns,
  state: {
    get sorting() {
      return sorting.value
    },
  },
  onSortingChange: (u) => (sorting.value = typeof u === 'function' ? u(sorting.value) : u),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const shownCount = computed(() => table.getSortedRowModel().rows.length)

// --- Add / inline edit ------------------------------------------------------
// `panel` is null when closed, the row object when editing, or the sentinel
// `'new'` when creating. One Modal + one BomGlobalForm covers both flows.
const panel = ref(null)
const saving = ref(false)

const isEditing = computed(() => panel.value && panel.value !== 'new')

function openAdd() {
  panel.value = 'new'
}
function openEdit(row) {
  panel.value = row
}

async function onSave(payload) {
  saving.value = true
  try {
    if (isEditing.value) {
      const { projectId: _drop, ...body } = payload
      await store.updateRow(panel.value.id, body)
      ui.success('BOM record updated')
    } else {
      const { projectId, ...body } = payload
      await store.createRow(projectId, body)
      ui.success('BOM record added')
    }
    panel.value = null
  } catch (e) {
    ui.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!window.confirm(`Delete "${row.deviceName || 'this record'}"?`)) return
  try {
    await store.deleteRow(row.id)
    ui.success('BOM record deleted')
  } catch (e) {
    ui.error(e.message)
  }
}

// --- Import (Excel) ---------------------------------------------------------
const importResult = ref(null)
const importing = ref(false)

async function onImportFile(file) {
  try {
    importResult.value = await parseBomInventoryExcel(file, projectsStore.projects)
  } catch (e) {
    ui.error(e.message)
  }
}

// Total price is a derived field: quantity × unitPrice. Apply the same formula
// the edit form's watcher uses, so imported rows display the computed total
// immediately — without needing an Edit → Save round-trip to materialize it.
function computedTotal(qty, unitPrice) {
  const q = qty === '' || qty == null ? null : Number(qty)
  const u = unitPrice === '' || unitPrice == null ? null : Number(unitPrice)
  return q != null && u != null && !isNaN(q) && !isNaN(u) ? q * u : null
}

async function confirmImport() {
  const rows = importResult.value?.valid || []
  if (!rows.length) return
  importing.value = true
  try {
    for (const r of rows) {
      const { projectId, ...body } = r
      body.totalPrice = computedTotal(body.quantity, body.unitPrice)
      await api.createRecord(projectId, 'bom', body)
    }
    await store.fetchAll()
    ui.success(`Imported ${rows.length} BOM record(s)`)
    importResult.value = null
  } catch (e) {
    ui.error(e.message)
  } finally {
    importing.value = false
  }
}

// --- Export (filtered + sorted set) -----------------------------------------
async function doExport(format) {
  const rows = table.getSortedRowModel().rows.map((r) => r.original)
  if (!rows.length) return
  try {
    if (format === 'excel') await exportBomInventoryExcel(rows)
    else exportBomInventoryPdf(rows)
    ui.success(`Exported ${rows.length} record(s) to ${format === 'excel' ? 'Excel' : 'PDF'}`)
  } catch (e) {
    ui.error(e.message)
  }
}

// --- BOM list picker + manager ---------------------------------------------
// `pickerList` is null when picker is closed, `'new'` to open in create mode,
// or a list summary object to open in edit mode.
const pickerList = ref(null)
const listsManagerOpen = ref(false)

function openListPicker(lst = null) {
  pickerList.value = lst ?? 'new'
}
function onPickerSaved() {
  pickerList.value = null
}
function onManagerOpenList(lst) {
  // Switch from manager to picker in edit mode.
  listsManagerOpen.value = false
  pickerList.value = lst
}

onMounted(() => {
  store.fetchAll().catch((e) => ui.error(e.message))
  // Ensure the project dropdown has data even on a direct /bom landing.
  if (!projectsStore.projects.length) {
    projectsStore.fetchAll().catch((e) => ui.error(e.message))
  }
})
</script>

<template>
  <div class="view register">
    <header class="masthead">
      <div class="dateline mono">
        <span>BOM&nbsp;&amp;&nbsp;Costing</span>
        <span class="sep">·</span>
        <span>Total records : {{ store.rows.length }}</span>
        <span class="sep">·</span>
        <span>{{ today }}</span>
      </div>

      <div class="masthead-row">
        <h1 class="masthead-title"><em>BOM</em>&nbsp;Inventory</h1>

        <div class="actions">
          <button type="button" class="btn sm add-btn" @click="openAdd">
            <span class="plus">+</span> Add New
          </button>
          <button type="button" class="btn sm ghost" @click="openListPicker()">
            <span class="plus">+</span> Create BOM List
          </button>
          <button type="button" class="btn sm ghost" @click="listsManagerOpen = true">
            Saved Lists
          </button>
          <ExportImportMenu
            :formats="['excel', 'pdf']"
            :rows="shownCount"
            import-enabled
            @export="doExport"
            @import-file="onImportFile"
          />
        </div>
      </div>

      <p class="masthead-sub">
        All recorded materials, products, and equipment across every project — search, sort, and export.
      </p>
    </header>

    <div class="toolbar">
      <input
        :value="store.q"
        class="search"
        type="search"
        placeholder="Search device, spec, category, supplier, project…"
        @input="store.setQuery($event.target.value)"
      />
    </div>

    <div class="byline mono">
      <span class="folio">{{ String(shownCount).padStart(2, '0') }}</span>
      record{{ shownCount === 1 ? '' : 's' }} in view
      <span class="of">of {{ store.rows.length }} on record</span>
    </div>

    <div class="ledger">
      <table>
        <thead>
          <tr v-for="hg in table.getHeaderGroups()" :key="hg.id">
            <th class="folio-col">№</th>
            <th
              v-for="header in hg.headers"
              :key="header.id"
              :class="{ sortable: header.column.getCanSort(), num: NUM_COLS.has(header.column.id) }"
              @click="header.column.getToggleSortingHandler()?.($event)"
            >
              <span class="th-label">
                <FlexRender :render="header.column.columnDef.header" :props="header.getContext()" />
                <span v-if="header.column.getCanSort()" class="sort-ind" :class="{ on: header.column.getIsSorted() }">
                  {{ header.column.getIsSorted() === 'asc' ? '▲' : header.column.getIsSorted() === 'desc' ? '▼' : '◆' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in table.getRowModel().rows" :key="row.id" class="row">
            <td class="folio-col mono">{{ String(idx + 1).padStart(2, '0') }}</td>
            <td
              v-for="cell in row.getVisibleCells()"
              :key="cell.id"
              :class="{ num: NUM_COLS.has(cell.column.id) }"
            >
              <FlexRender :render="cell.column.columnDef.cell ?? cell.column.columnDef.accessorKey" :props="cell.getContext()" />
            </td>
          </tr>
          <tr v-if="store.loading">
            <td :colspan="columns.length + 1" class="empty">Loading…</td>
          </tr>
          <tr v-else-if="!table.getRowModel().rows.length">
            <td :colspan="columns.length + 1" class="empty">
              <span class="empty-mark">—</span>
              No BOM records match the current view.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Modal
      v-if="panel"
      :title="isEditing ? `Edit BOM — ${panel.projectName || ''}` : 'Add BOM record'"
      wide
      @close="panel = null"
    >
      <BomGlobalForm
        :record="isEditing ? panel : null"
        :submitting="saving"
        @submit="onSave"
        @cancel="panel = null"
      />
    </Modal>

    <BomListPicker
      v-if="pickerList"
      :list="pickerList === 'new' ? null : pickerList"
      @close="pickerList = null"
      @saved="onPickerSaved"
    />

    <BomListsManager
      v-if="listsManagerOpen"
      @close="listsManagerOpen = false"
      @open-list="onManagerOpenList"
    />

    <ImportResultModal
      v-if="importResult"
      title="Import BOM"
      :result="importResult"
      :importing="importing"
      @close="importResult = null"
      @confirm="confirmImport"
    />
  </div>
</template>

<style scoped>
.register {
  --serif: var(--font);
  --rule: color-mix(in srgb, var(--text) 78%, transparent);
}

.masthead {
  border-top: 2px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 12px 0 16px;
  margin-bottom: 18px;
}
.dateline {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--text-dim);
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}
.dateline .sep { color: var(--accent); }

.masthead-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}
.masthead-title {
  font-family: var(--serif);
  font-weight: 500;
  font-size: clamp(34px, 5vw, 52px);
  line-height: .98;
  letter-spacing: -.015em;
  color: var(--text);
  margin: 0;
}
.masthead-title em { font-style: italic; font-weight: 600; color: var(--accent-dim); }
.masthead-sub {
  font-family: var(--serif);
  font-size: 15px;
  font-style: italic;
  color: var(--text-dim);
  margin-top: 10px;
  max-width: 60ch;
}
.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding-bottom: 4px; }

.toolbar { margin: 4px 0 2px; }
.search {
  width: 100%;
  max-width: 420px;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 13px;
}
.search:focus { outline: none; border-color: var(--accent); }

.byline {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin: 14px 0 10px;
}
.byline .folio { font-size: 13px; color: var(--accent-dim); font-weight: 700; }
.byline .of { color: color-mix(in srgb, var(--text-dim) 70%, transparent); }

.ledger {
  overflow-x: auto;
  border-top: 1.5px solid var(--rule);
  border-bottom: 1.5px solid var(--rule);
}
table { width: 100%; border-collapse: collapse; min-width: 1000px; }

thead th {
  text-align: left;
  padding: 11px 12px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--text-dim);
  border-bottom: 1.5px solid var(--rule);
  user-select: none;
  white-space: nowrap;
  vertical-align: bottom;
}
.th-label { display: inline-flex; align-items: center; gap: 6px; }
th.sortable { cursor: pointer; transition: color .12s; }
th.sortable:hover { color: var(--text); }
th.num, td.num { text-align: right; }
th.num .th-label { flex-direction: row-reverse; }

.sort-ind { font-size: 8px; opacity: 0; color: var(--accent); transition: opacity .12s; }
th.sortable:hover .sort-ind { opacity: .35; }
.sort-ind.on { opacity: 1; }

.folio-col {
  width: 1%;
  text-align: right;
  padding-right: 10px !important;
  color: color-mix(in srgb, var(--text-dim) 65%, transparent);
  font-size: 11px;
}

tbody td {
  padding: 11px 12px;
  font-size: 13px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  white-space: nowrap;
}
td.num {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  letter-spacing: -.01em;
}
.row:hover { background: color-mix(in srgb, var(--accent) 5%, var(--surface)); }
tbody tr:last-child td { border-bottom: none; }

.add-btn .plus { font-size: 15px; font-weight: 700; line-height: 1; }

.row-actions { display: inline-flex; gap: 6px; }
.mini {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  border-radius: 6px;
  padding: 4px 9px;
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: color .12s, border-color .12s;
}
.mini:hover { color: var(--accent); border-color: var(--accent); }
.mini.danger:hover { color: #c0392b; border-color: #c0392b; }

.empty {
  text-align: center;
  color: var(--text-dim);
  padding: 48px;
  font-family: var(--serif);
  font-style: italic;
  font-size: 15px;
}
.empty-mark { display: block; font-size: 22px; color: var(--border); margin-bottom: 6px; }

:deep(.project-cell) {
  font-family: var(--serif);
  font-weight: 600;
  font-size: 14px;
}
</style>

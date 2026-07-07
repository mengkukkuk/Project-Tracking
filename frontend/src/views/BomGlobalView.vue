<script setup>
import { ref, shallowRef, h, computed, defineComponent, watch, onMounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { ModuleRegistry, AllCommunityModule, themeMaterial } from 'ag-grid-community'
import { useBomStore } from '@/stores/bom'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import AppIcon from '@/components/AppIcon.vue'
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
import { RECORD_SCHEMAS } from '@/schemas/records'
import { api } from '@/api'

// Module registration is global; ag-grid dedupes, so multiple views registering
// AllCommunityModule is harmless.
ModuleRegistry.registerModules([AllCommunityModule])

const store = useBomStore()
const projectsStore = useProjectsStore()
const ui = useUiStore()
const { date } = useFormat()

const gridApi = shallowRef(null)

const today = new Date()
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  .toUpperCase()

const num = (v) => (v == null || v === '' ? '—' : Number(v).toLocaleString())
const dash = (p) => (p.value == null || p.value === '' ? '—' : p.value)

// --- Filters -----------------------------------------------------------------
// Facet options are derived from the loaded rows (category/supplier) or the
// projects store (project); mirrors ProjectFilters.vue's search+selects+active
// chips pattern, but filtering here is purely client-side (no server round-trip).
const categoryOptions = computed(() =>
  [...new Set(store.rows.map((r) => r.category).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
)
const supplierOptions = computed(() =>
  [...new Set(store.rows.map((r) => r.supplier).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
)
const projectFilterOptions = computed(() =>
  [...projectsStore.projects].sort((a, b) => (a.name || '').localeCompare(b.name || '')),
)

const filtered = computed(() => {
  const { q, category, supplier, projectId } = store.filters
  const needle = q.trim().toLowerCase()
  return store.rows.filter((r) => {
    if (category && r.category !== category) return false
    if (supplier && r.supplier !== supplier) return false
    if (projectId && String(r.projectId) !== String(projectId)) return false
    if (!needle) return true
    return ['deviceName', 'spec', 'category', 'supplier', 'projectName'].some((k) =>
      String(r[k] || '').toLowerCase().includes(needle),
    )
  })
})

// Local echo of the search text, debounced into the store — same pattern as
// ProjectFilters.vue's onSearch, so "Clear all" (which replaces store.filters
// wholesale) stays in sync via the watcher below.
const qInput = ref(store.filters.q)
watch(
  () => store.filters.q,
  (value) => {
    if (value !== qInput.value) qInput.value = value || ''
  },
)
let searchTimer
function onSearch(value) {
  qInput.value = value
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => store.setFilter({ q: value.trim() }), 250)
}

const activeFilters = computed(() => {
  const items = []
  if (store.filters.q) items.push(['q', `Search: ${store.filters.q}`])
  if (store.filters.category) items.push(['category', store.filters.category])
  if (store.filters.supplier) items.push(['supplier', store.filters.supplier])
  if (store.filters.projectId) {
    const proj = projectsStore.projects.find((p) => String(p.id) === String(store.filters.projectId))
    items.push(['projectId', proj?.name || 'Project'])
  }
  return items
})

function clearOne(key) {
  store.setFilter({ [key]: '' })
}

// Every colour is a live var() into assets/main.css, so dark mode / accent
// recolour the grid for free — no second theme to maintain.
const gridTheme = themeMaterial.withParams({
  accentColor: 'var(--accent)',
  backgroundColor: 'var(--surface)',
  foregroundColor: 'var(--text)',
  borderColor: 'var(--border)',
  headerBackgroundColor: 'var(--bg)',
  headerTextColor: 'var(--text-dim)',
  headerFontWeight: 600,
  oddRowBackgroundColor: 'transparent',
  rowHoverColor: 'color-mix(in srgb, var(--accent) 5%, var(--surface))',
  fontFamily: "'IBM Plex Sans Thai', system-ui, sans-serif",
  fontSize: 13,
  headerFontSize: 10,
  wrapperBorder: false,
  headerRowBorder: { color: 'var(--border)', width: 1.5 },
  rowBorder: { color: 'var(--border)', width: 1 },
  columnBorder: false,
  spacing: 7,
})

const rowHeight = 46
const headerHeight = 40

// cellRenderers are thin defineComponent wrappers so the presentational look
// stays in the view; ag-grid injects `params` (with .value/.data).
const PrimaryCell = defineComponent({
  props: ['params'],
  render() {
    return h('strong', { class: 'primary-cell' }, this.params.value || '—')
  },
})
const TotalCell = defineComponent({
  props: ['params'],
  render() {
    return h('span', { class: 'total-figure' }, num(this.params.value))
  },
})
const ActionsCell = defineComponent({
  props: ['params'],
  render() {
    const row = this.params.data
    // Icon-only pill buttons; each carries title + aria-label for a11y/tooltip.
    const iconBtn = (icon, label, handler, extraClass) =>
      h(
        'button',
        {
          class: ['mini', 'icon-btn', extraClass].filter(Boolean).join(' '),
          type: 'button',
          title: label,
          'aria-label': label,
          onClick: (e) => {
            e.stopPropagation()
            handler(row)
          },
        },
        [h(AppIcon, { name: icon, size: 15 })],
      )
    return h('div', { class: 'row-actions' }, [
      iconBtn('edit', 'Edit', openEdit),
      iconBtn('copy', 'Duplicate', duplicate),
      iconBtn('trash', 'Delete', remove, 'danger'),
    ])
  },
})

const defaultColDef = { sortable: true, resizable: true, suppressMovable: true }

const columnDefs = [
  {
    colId: 'folio', headerName: '№', width: 64, pinned: 'left',
    sortable: false, resizable: false,
    valueGetter: (p) => p.node.rowIndex + 1,
    valueFormatter: (p) => String(p.value).padStart(2, '0'),
    cellClass: 'folio-col mono', headerClass: 'folio-col',
  },
  { field: 'deviceName', headerName: 'Device name', pinned: 'left', flex: 1.4, minWidth: 160, sort: 'asc', cellRenderer: PrimaryCell },
  { field: 'projectName', headerName: 'Project', flex: 1.2, minWidth: 130, valueFormatter: dash },
  { field: 'category', headerName: 'Category', width: 96, valueFormatter: dash },
  { field: 'version', headerName: 'Version', width: 84, valueFormatter: dash },
  { field: 'quantity', headerName: 'Qty', width: 68, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
  { field: 'unit', headerName: 'Unit', width: 68, valueFormatter: dash },
  { field: 'position', headerName: 'Position', width: 96, valueFormatter: dash },
  { field: 'unitPrice', headerName: 'Unit price', width: 96, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
  { field: 'totalPrice', headerName: 'Total price', width: 104, cellClass: 'num', headerClass: 'num', cellRenderer: TotalCell },
  { field: 'leadTime', headerName: 'Lead time', width: 96, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
  { field: 'supplier', headerName: 'Supplier', width: 112, valueFormatter: dash },
  { field: 'dateApprove', headerName: 'Approved on', width: 108, valueFormatter: (p) => date(p.value) },
  { colId: 'actions', headerName: '', width: 118, pinned: 'right', sortable: false, resizable: false, cellRenderer: ActionsCell, cellClass: 'actions-cell' },
]

const shownCount = computed(() => filtered.value.length)
const noRowsTemplate = '<div class="empty"><span class="empty-mark">—</span>No BOM records match the current view.</div>'
const loadingTemplate = '<div class="empty">Loading…</div>'

function onGridReady(e) {
  gridApi.value = e.api
  if (store.loading) e.api.showLoadingOverlay()
}

// ag-grid owns overlay display; keep it in sync with the store's loading flag
// and the filtered set (autoHeight grids don't auto-toggle the no-rows overlay).
watch(
  () => [store.loading, filtered.value.length],
  ([loading, count]) => {
    if (!gridApi.value) return
    if (loading) gridApi.value.showLoadingOverlay()
    else if (!count) gridApi.value.showNoRowsOverlay()
    else gridApi.value.hideOverlay()
  },
)

// Export must mirror what's on screen (current sort + filter), so read from the
// grid rather than the store.
function sortedRows() {
  const rows = []
  gridApi.value?.forEachNodeAfterFilterAndSort((n) => rows.push(n.data))
  return rows
}

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

// Duplicate: create a fresh record in the same project from a copy of the row's
// BOM fields (id/projectId/projectName are dropped — createRow assigns them).
async function duplicate(row) {
  try {
    const body = {}
    for (const f of RECORD_SCHEMAS.bom.fields) {
      body[f.key] = row[f.key] ?? (f.type === 'number' ? null : f.type === 'checkbox' ? false : '')
    }
    await store.createRow(row.projectId, body)
    ui.success('BOM record duplicated')
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
  const rows = sortedRows()
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
        <h1 class="masthead-title">BOM Inventory</h1>

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
        แสดงรายการ BOM ที่มีการบันทึกไว้ || เพิ่มอุปกรณ์, สร้างรายการ, Export excel/PDF
      </p>
    </header>

    <section class="filters" aria-label="BOM filters">
      <div class="search-box">
        <AppIcon name="search" :size="16" />
        <input
          :value="qInput"
          type="search"
          placeholder="Search by device, spec, category, supplier, project…"
          @input="onSearch($event.target.value)"
        />
      </div>

      <div class="selects">
        <label>
          <span>Category</span>
          <select :value="store.filters.category" @change="store.setFilter({ category: $event.target.value })">
            <option value="">Any category</option>
            <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>
          <span>Supplier</span>
          <select :value="store.filters.supplier" @change="store.setFilter({ supplier: $event.target.value })">
            <option value="">Any supplier</option>
            <option v-for="s in supplierOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>
          <span>Project</span>
          <select :value="store.filters.projectId" @change="store.setFilter({ projectId: $event.target.value })">
            <option value="">Any project</option>
            <option v-for="p in projectFilterOptions" :key="p.id" :value="String(p.id)">{{ p.name }}</option>
          </select>
        </label>
      </div>

      <div v-if="activeFilters.length" class="active">
        <span class="active-label"><AppIcon name="filter" :size="14" /> Active</span>
        <button v-for="[key, label] in activeFilters" :key="key" type="button" class="active-chip" @click="clearOne(key)">
          {{ label }}
          <AppIcon name="close" :size="12" />
        </button>
        <button type="button" class="clear" @click="store.clearFilters()">Clear all</button>
      </div>
    </section>

    <div class="byline mono">
      <span class="folio">{{ String(shownCount).padStart(2, '0') }}</span>
      record{{ shownCount === 1 ? '' : 's' }} in view
      <span class="of">of {{ store.rows.length }} on record</span>
    </div>

    <div class="ledger" :style="{ '--row-h': rowHeight + 'px' }">
      <AgGridVue
        class="grid"
        :theme="gridTheme"
        :columnDefs="columnDefs"
        :rowData="filtered"
        :defaultColDef="defaultColDef"
        :rowHeight="rowHeight"
        :headerHeight="headerHeight"
        domLayout="autoHeight"
        :suppressCellFocus="true"
        :overlayNoRowsTemplate="noRowsTemplate"
        :overlayLoadingTemplate="loadingTemplate"
        @grid-ready="onGridReady"
      />
    </div>

    <Modal
      v-if="panel"
      :title="isEditing ? `Edit BOM — ${panel.deviceName || ''}` : 'Add BOM record'"
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

.filters {
  display: grid;
  gap: 10px;
  margin: 4px 0 2px;
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
.search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(20, 184, 166, .15); }

.selects,
.active {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.selects label { display: grid; gap: 4px; }
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

.active { padding-top: 2px; }
.active-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 700;
}
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
.active-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
}
.clear { color: var(--text-dim); }
.clear:hover { border-color: var(--accent); color: var(--accent); }

@media (min-width: 1100px) {
  .filters {
    grid-template-columns: minmax(280px, 420px) 1fr;
    align-items: start;
  }
  .selects,
  .active { grid-column: 1 / -1; }
}

@media (max-width: 640px) {
  .filters { gap: 8px; }
  .search-box { width: 100%; min-height: 38px; }
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
  border-top: 1.5px solid var(--rule);
  border-bottom: 1.5px solid var(--rule);
}
.grid { width: 100%; }

:deep(.ag-header-cell-text) {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .12em;
}
:deep(.ag-header-cell.num .ag-header-cell-label) { justify-content: flex-end; }
:deep(.ag-cell.num) {
  font-family: var(--font);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  letter-spacing: -.01em;
  justify-content: flex-end;
  text-align: right;
}
:deep(.folio-col) {
  color: color-mix(in srgb, var(--text-dim) 65%, transparent);
  font-size: 11px;
  justify-content: flex-end;
  text-align: right;
}
:deep(.ag-cell.actions-cell) {
  justify-content: flex-end;
  /* Tighter than the grid's default cell padding so three icon buttons fit. */
  padding-left: 10px;
  padding-right: 12px;
}

:deep(.total-figure) {
  font-weight: 700;
  color: var(--accent-dim);
}

.add-btn {
  box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 35%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, .18);
}
.add-btn .plus { font-size: 15px; font-weight: 700; line-height: 1; }

:deep(.row-actions) { display: inline-flex; gap: 6px; }
:deep(.mini) {
  box-sizing: border-box;
  height: calc(var(--row-h) * 0.5);
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  border-radius: 999px;
  padding: 0 11px;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: .02em;
  cursor: pointer;
  transition: color .12s, border-color .12s, background-color .12s;
}
:deep(.mini:hover) { color: var(--accent-dim); border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--surface)); }
:deep(.mini:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
:deep(.mini.danger:hover) { color: #c0392b; border-color: #c0392b; background: color-mix(in srgb, #c0392b 8%, var(--surface)); }

/* Icon-only variant: square footprint, centred glyph — used for the row actions. */
:deep(.mini.icon-btn) {
  width: calc(var(--row-h) * 0.5);
  padding: 0;
  justify-content: center;
  color: var(--text-dim);
}

.empty {
  text-align: center;
  color: var(--text-dim);
  padding: 48px;
  font-family: var(--serif);
  font-style: italic;
  font-size: 15px;
}
.empty-mark { display: block; font-size: 22px; color: var(--border); margin-bottom: 6px; }

:deep(.primary-cell) {
  font-family: var(--serif);
  font-weight: 600;
  font-size: 14px;
}
</style>

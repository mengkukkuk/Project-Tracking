<script setup>
import { ref, shallowRef, h, computed, defineComponent, watch, onMounted, onUnmounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { ModuleRegistry, AllCommunityModule, themeMaterial } from 'ag-grid-community'
import { useBomStore } from '@/stores/bom'
import { useInventoryStore } from '@/stores/inventory'
import { useProjectsStore } from '@/stores/projects'
import { useLookupsStore } from '@/stores/lookups'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useFormat } from '@/composables/useFormat'
import AppIcon from '@/components/AppIcon.vue'
import ExportImportMenu from '@/components/ExportImportMenu.vue'
import ImportResultModal from '@/components/ImportResultModal.vue'
import Modal from '@/components/Modal.vue'
import BomGlobalForm from '@/components/BomGlobalForm.vue'
import BomListPicker from '@/components/BomListPicker.vue'
import BomListsManager from '@/components/BomListsManager.vue'
import BomExportDocsModal from '@/components/BomExportDocsModal.vue'
import {
  exportBomInventoryExcel,
  exportBomInventoryPdf,
  exportInventoryCatalogueExcel,
  exportInventoryCataloguePdf,
  parseBomInventoryExcel,
} from '@/utils/recordExport'
import { RECORD_SCHEMAS } from '@/schemas/records'
import { api } from '@/api'

// Module registration is global; ag-grid dedupes, so multiple views registering
// AllCommunityModule is harmless.
ModuleRegistry.registerModules([AllCommunityModule])

const store = useBomStore()
const invStore = useInventoryStore()
const projectsStore = useProjectsStore()
const lookupsStore = useLookupsStore()
const ui = useUiStore()
const auth = useAuthStore()
const { date } = useFormat()

// --- INVENTORY toggle --------------------------------------------------------
// OFF: the grid shows bom_and_costing rows (per-project BOM records, default).
// ON: it shows the shared inventory catalogue instead. Same filters/search,
// minus the Project filter (a catalogue entry is project-independent).
const inventoryMode = ref(false)
// Backend gates writes on inventory.update / inventory.delete; hiding here is
// UI-advisory only.
const canEditInventory = computed(
  () => auth.hasPermission('inventory.update') || auth.hasPermission('inventory.delete'),
)

function toggleInventory() {
  inventoryMode.value = !inventoryMode.value
  if (inventoryMode.value) {
    // Refetch on every switch-on: cheap, and keeps the catalogue fresh.
    invStore.fetchAll().catch((e) => ui.error(e.message))
    // A project filter is meaningless on catalogue rows — clear it so no
    // invisible filter (or orphaned chip) lingers while the select is hidden.
    if (store.filters.projectId) store.setFilter({ projectId: '' })
  }
}

const gridApi = shallowRef(null)

// Below 760px (App.vue's mobile-shell breakpoint) keep the grid at autoHeight so
// the page scrolls naturally; on desktop it uses `normal` layout inside a
// viewport-tall flex column, so its rows scroll internally while the filter panel
// and column header stay locked in place.
const mq = window.matchMedia('(max-width: 760px)')
const isMobile = ref(mq.matches)
const onMq = (e) => {
  isMobile.value = e.matches
}
mq.addEventListener('change', onMq)
onUnmounted(() => mq.removeEventListener('change', onMq))

const today = new Date()
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  .toUpperCase()

const num = (v) => (v == null || v === '' ? '—' : Number(v).toLocaleString())
const dash = (p) => (p.value == null || p.value === '' ? '—' : p.value)

// --- Filters -----------------------------------------------------------------
// Category/Type options come from the lookup_type/lookup_value taxonomy
// (lookupsStore), not from row values — the taxonomy is the source of truth
// even though most legacy `category` text is free-form. Supplier/project still
// derive from loaded rows / the projects store. Mirrors ProjectFilters.vue's
// search+selects+active chips pattern; filtering here is purely client-side.
const norm = (s) => String(s || '').trim().toLowerCase()

// Rows behind the grid — bom records or the inventory catalogue per the toggle.
const activeRows = computed(() => (inventoryMode.value ? invStore.rows : store.rows))

const categoryOptions = computed(() => lookupsStore.types)
const typeOptions = computed(() => lookupsStore.typeByCode(store.filters.category)?.values || [])
const supplierOptions = computed(() =>
  [...new Set(activeRows.value.map((r) => r.supplier).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  ),
)
const projectFilterOptions = computed(() =>
  [...projectsStore.projects].sort((a, b) => (a.name || '').localeCompare(b.name || '')),
)

// A row's free-text `category` matches a selected taxonomy Category when it
// case-insensitively equals the type's own code/name/description, or any of
// that type's value codes/display names (legacy rows only ever carry a
// type-level value, never a value-level one — see plan notes).
function categoryMatchSet(typeCode) {
  const t = lookupsStore.typeByCode(typeCode)
  if (!t) return null
  const set = new Set([t.code, t.name, t.description].filter(Boolean).map(norm))
  for (const v of t.values || []) {
    if (v.code) set.add(norm(v.code))
    if (v.displayName) set.add(norm(v.displayName))
  }
  return set
}

function typeMatchSet(typeCode, valueCode) {
  const v = lookupsStore.typeByCode(typeCode)?.values?.find((x) => x.code === valueCode)
  if (!v) return null
  return new Set([v.code, v.displayName].filter(Boolean).map(norm))
}

function onCategoryChange(value) {
  store.setFilter({ category: value, type: '' })
}

const filtered = computed(() => {
  const { q, category, type, supplier, projectId } = store.filters
  const needle = q.trim().toLowerCase()
  // Resolve the selected filter codes to their lookup rows so we can match on
  // the stored FK ids (new rows) as well as on text (legacy/imported rows).
  const selType = category ? lookupsStore.typeByCode(category) : null
  const selValue = selType && type ? selType.values?.find((v) => v.code === type) : null
  const catSet = category ? categoryMatchSet(category) : null
  const typeSet = category && type ? typeMatchSet(category, type) : null
  // Catalogue rows have no projectName; bom rows search it too.
  const searchKeys = inventoryMode.value
    ? ['deviceName', 'spec', 'category', 'type', 'supplier']
    : ['deviceName', 'spec', 'category', 'type', 'supplier', 'projectName']
  return activeRows.value.filter((r) => {
    // A row matches a selected Category/Type when its stored id matches OR its
    // resolved/legacy text matches — the id path is what lets newly-saved rows
    // (and the Type filter) resolve, while text keeps legacy rows working.
    if (category && !((selType && r.categoryId === selType.id) || (catSet && catSet.has(norm(r.category)))))
      return false
    if (type && !((selValue && r.typeId === selValue.id) || (typeSet && typeSet.has(norm(r.type)))))
      return false
    if (supplier && r.supplier !== supplier) return false
    if (!inventoryMode.value && projectId && String(r.projectId) !== String(projectId))
      return false
    if (!needle) return true
    return searchKeys.some((k) => String(r[k] || '').toLowerCase().includes(needle))
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
  if (store.filters.category) {
    const t = lookupsStore.typeByCode(store.filters.category)
    items.push(['category', t?.description || t?.name || store.filters.category])
  }
  if (store.filters.type) {
    const v = lookupsStore
      .typeByCode(store.filters.category)
      ?.values?.find((x) => x.code === store.filters.type)
    items.push(['type', v?.displayName || store.filters.type])
  }
  if (store.filters.supplier) items.push(['supplier', store.filters.supplier])
  if (store.filters.projectId) {
    const proj = projectsStore.projects.find((p) => String(p.id) === String(store.filters.projectId))
    items.push(['projectId', proj?.name || 'Project'])
  }
  return items
})

function clearOne(key) {
  // Type is meaningless without a Category, so clearing Category also clears Type.
  if (key === 'category') store.setFilter({ category: '', type: '' })
  else store.setFilter({ [key]: '' })
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
    // Inventory mode: no Duplicate (a catalogue entry is already the shared
    // master copy); the whole column is omitted for users without the
    // inventory.* permissions, so no per-button gate is needed here.
    const buttons = inventoryMode.value
      ? [iconBtn('edit', 'Edit', openEdit), iconBtn('trash', 'Delete', remove, 'danger')]
      : [
          iconBtn('edit', 'Edit', openEdit),
          iconBtn('copy', 'Duplicate', duplicate),
          iconBtn('trash', 'Delete', remove, 'danger'),
        ]
    return h('div', { class: 'row-actions' }, buttons)
  },
})

const defaultColDef = { sortable: true, resizable: true, suppressMovable: true }

const folioCol = {
  colId: 'folio', headerName: '№', width: 64, pinned: 'left',
  sortable: false, resizable: false,
  valueGetter: (p) => p.node.rowIndex + 1,
  valueFormatter: (p) => String(p.value).padStart(2, '0'),
  cellClass: 'folio-col mono', headerClass: 'folio-col',
}
const actionsCol = { colId: 'actions', headerName: '', width: 118, pinned: 'right', sortable: false, resizable: false, cellRenderer: ActionsCell, cellClass: 'actions-cell' }

// Computed so ag-grid swaps column sets when the INVENTORY toggle flips.
// Catalogue entries have no quantity/total/project/position/dateApprove.
const columnDefs = computed(() =>
  inventoryMode.value
    ? [
        folioCol,
        { field: 'deviceName', headerName: 'Device name', pinned: 'left', flex: 1.4, minWidth: 160, sort: 'asc', cellRenderer: PrimaryCell },
        { field: 'version', headerName: 'Version', width: 100, valueFormatter: dash },
        { field: 'category', headerName: 'Category', width: 110, valueFormatter: dash },
        { field: 'type', headerName: 'Type', flex: 1, minWidth: 130, valueFormatter: dash },
        { field: 'unit', headerName: 'Unit', minWidth: 75, maxWidth: 80, valueFormatter: dash },
        { field: 'unitPrice', headerName: 'Unit price', width: 126, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
        { field: 'supplier', headerName: 'Supplier', width: 130, valueFormatter: dash },
        { field: 'leadTime', headerName: 'Lead time', width: 96, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
        ...(canEditInventory.value ? [{ ...actionsCol, width: 88 }] : []),
      ]
    : [
        folioCol,
        { field: 'deviceName', headerName: 'Device name', pinned: 'left', flex: 1.4, minWidth: 160, sort: 'asc', cellRenderer: PrimaryCell },
        { field: 'version', headerName: 'Version', width: 100, valueFormatter: dash },
        { field: 'quantity', headerName: 'Qty', minWidth: 65, maxWidth: 75, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
        { field: 'unit', headerName: 'Unit', minWidth: 75, maxWidth: 80, valueFormatter: dash },
        { field: 'unitPrice', headerName: 'Unit price', width: 126, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
        { field: 'totalPrice', headerName: 'Total price', width: 126, cellClass: 'num', headerClass: 'num', cellRenderer: TotalCell },
        { field: 'category', headerName: 'Category', width: 96, valueFormatter: dash },
        { field: 'type', headerName: 'Type', width: 120, valueFormatter: dash },
        { field: 'projectName', headerName: 'Project', flex: 1.2, minWidth: 120, valueFormatter: dash },
        { field: 'position', headerName: 'Position', minWidth: 80, maxWidth: 100, valueFormatter: dash },
        { field: 'supplier', headerName: 'Supplier', width: 112, valueFormatter: dash },
        { field: 'leadTime', headerName: 'Lead time', width: 96, cellClass: 'num', headerClass: 'num', valueFormatter: (p) => num(p.value) },
        { field: 'dateApprove', headerName: 'Approved on', width: 108, valueFormatter: (p) => date(p.value) },
        actionsCol,
      ],
)
//
const shownCount = computed(() => filtered.value.length)
const noRowsTemplate = '<div class="empty"><span class="empty-mark">—</span>No records match the current view.</div>'
const loadingTemplate = '<div class="empty">Loading…</div>'

const gridLoading = computed(() => (inventoryMode.value ? invStore.loading : store.loading))

function onGridReady(e) {
  gridApi.value = e.api
  if (gridLoading.value) e.api.showLoadingOverlay()
}

// ag-grid owns overlay display; keep it in sync with the active store's loading
// flag and the filtered set (autoHeight grids don't auto-toggle the no-rows
// overlay).
watch(
  () => [gridLoading.value, filtered.value.length],
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

// --- Device details card ----------------------------------------------------
// Read-only quick view opened by clicking anywhere on a row. Bound to
// cell-clicked (not row-clicked) so the actions column — including its empty
// space — never triggers it; the icon buttons also stopPropagation.
const detailCard = ref(null)

function onCellClicked(e) {
  if (e.colDef?.colId === 'actions') return
  detailCard.value = e.data
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

// The subset of the flat form payload that maps onto a catalogue entry —
// project-only keys (quantity/position/dateApprove/totalPrice/projectId) are
// stripped before hitting /api/inventory.
const INVENTORY_KEYS = [
  'categoryId', 'typeId', 'deviceName', 'version', 'spec',
  'unit', 'unitPrice', 'supplier', 'leadTime',
]
const pickInventory = (payload) =>
  Object.fromEntries(INVENTORY_KEYS.map((k) => [k, payload[k] ?? null]))

async function onSave(payload) {
  saving.value = true
  try {
    if (isEditing.value) {
      if (inventoryMode.value) {
        await invStore.updateRow(panel.value.id, pickInventory(payload))
        ui.success('Inventory entry updated')
      } else {
        // Keep projectId in the payload so the edit can reparent the record to
        // a different project (the BOM PATCH endpoint accepts projectId).
        await store.updateRow(panel.value.id, payload)
        ui.success('BOM record updated')
      }
      panel.value = null
    } else {
      // Inventory-first, sequenced (not atomic): the catalogue entry is the
      // system of record; the optional project copy is best-effort on top.
      await invStore.createRow(pickInventory(payload))
      ui.success('Added to inventory')
      if (payload.projectId) {
        try {
          const { projectId, ...body } = payload
          await store.createRow(projectId, body)
          ui.success('BOM row added to the project')
        } catch (e) {
          ui.error(`Inventory saved, but the project BOM copy failed: ${e.message}`)
        }
      }
      // Close even on partial success — resubmitting would duplicate the
      // catalogue entry.
      panel.value = null
    }
  } catch (e) {
    ui.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (inventoryMode.value) {
    const msg =
      `Delete "${row.deviceName || 'this entry'}" from the inventory catalogue? ` +
      'It will also be removed from any saved BOM lists that reference it.'
    if (!window.confirm(msg)) return
    try {
      await invStore.deleteRow(row.id)
      ui.success('Inventory entry deleted')
    } catch (e) {
      ui.error(e.message)
    }
    return
  }
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
    if (inventoryMode.value) {
      if (format === 'excel') await exportInventoryCatalogueExcel(rows)
      else exportInventoryCataloguePdf(rows)
    } else if (format === 'excel') {
      await exportBomInventoryExcel(rows)
    } else {
      exportBomInventoryPdf(rows)
    }
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
// Context for the PDF doc-picker modal ({ project, listName, rows }); null when closed.
const docExportCtx = ref(null)

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
  if (!lookupsStore.types.length) {
    lookupsStore.fetchAll().catch((e) => ui.error(e.message))
  }
})
</script>

<template>
  <div class="view register" :class="{ 'is-desktop': !isMobile }">
    <header class="masthead">
      <!--div class="dateline mono">
        <span>BOM&nbsp;&amp;&nbsp;Costing</span>
        <span class="sep">·</span>
        <span>Total records : {{ store.rows.length }}</span>
        <span class="sep">·</span>
        <span>{{ today }}</span>
      </div-->

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
            :import-enabled="!inventoryMode"
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
        <label class="selects">
          <span>Category</span>
          <select :value="store.filters.category" @change="onCategoryChange($event.target.value)">
            <option value="">Any category</option>
            <option v-for="t in categoryOptions" :key="t.code" :value="t.code">
              {{ t.description || t.name }}
            </option>
          </select>
        </label>
        <label>
          <span>Type</span>
          <select
            :value="store.filters.type"
            :disabled="!store.filters.category"
            @change="store.setFilter({ type: $event.target.value })"
          >
            <option value="">Any type</option>
            <option v-for="v in typeOptions" :key="v.code" :value="v.code">{{ v.displayName }}</option>
          </select>
        </label>
        <label>
          <span>Supplier</span>
          <select :value="store.filters.supplier" @change="store.setFilter({ supplier: $event.target.value })">
            <option value="">Any supplier</option>
            <option v-for="s in supplierOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label v-if="!inventoryMode">
          <span>Project</span>
          <select :value="store.filters.projectId" @change="store.setFilter({ projectId: $event.target.value })">
            <option value="">Any project</option>
            <option v-for="p in projectFilterOptions" :key="p.id" :value="String(p.id)">{{ p.name }}</option>
          </select>
        </label>
      </div>

      <button
        type="button"
        class="inv-toggle"
        :class="{ 'is-on': inventoryMode }"
        :aria-pressed="inventoryMode"
        title="Toggle between BOM records and the inventory catalogue"
        @click="toggleInventory"
      >
        <AppIcon name="table" :size="13" /> INVENTORY
      </button>

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
      {{ inventoryMode ? 'inventory item' : 'record' }}{{ shownCount === 1 ? '' : 's' }} in view
      <span class="of">of {{ activeRows.length }} on record</span>
    </div>

    <div v-if="!isMobile" class="ledger" :style="{ '--row-h': rowHeight + 'px' }">
      <AgGridVue
        class="grid"
        :theme="gridTheme"
        :columnDefs="columnDefs"
        :rowData="filtered"
        :defaultColDef="defaultColDef"
        :rowHeight="rowHeight"
        :headerHeight="headerHeight"
        :domLayout="isMobile ? 'autoHeight' : 'normal'"
        :suppressCellFocus="true"
        :overlayNoRowsTemplate="noRowsTemplate"
        :overlayLoadingTemplate="loadingTemplate"
        @grid-ready="onGridReady"
        @cell-clicked="onCellClicked"
      />
    </div>

    <!-- Mobile: stacked cards instead of the wide grid --------------------- -->
    <div v-else class="card-list">
      <button
        v-for="(r, i) in filtered"
        :key="r.id"
        type="button"
        class="bom-card card"
        @click="detailCard = r"
      >
        <div class="bc-top">
          <span class="bc-folio mono">{{ String(i + 1).padStart(2, '0') }}</span>
          <strong class="bc-name">{{ r.deviceName || '—' }}</strong>
          <span v-if="!inventoryMode || canEditInventory" class="bc-actions">
            <button class="mini icon-btn" type="button" title="Edit" aria-label="Edit" @click.stop="openEdit(r)">
              <AppIcon name="edit" :size="15" />
            </button>
            <button class="mini icon-btn danger" type="button" title="Delete" aria-label="Delete" @click.stop="remove(r)">
              <AppIcon name="trash" :size="15" />
            </button>
          </span>
        </div>
        <div class="bc-chips">
          <span v-if="!inventoryMode && r.projectName" class="bc-chip lc-chip">{{ r.projectName }}</span>
          <span v-if="r.category" class="bc-chip lc-chip">{{ r.category }}</span>
          <span v-if="r.type" class="bc-chip lc-chip">{{ r.type }}</span>
          <span v-if="r.supplier" class="bc-chip lc-chip">{{ r.supplier }}</span>
        </div>
        <div class="bc-figures">
          <span v-if="!inventoryMode"><em>Qty</em> {{ num(r.quantity) }}{{ r.unit ? ' ' + r.unit : '' }}</span>
          <span><em>Unit</em> {{ num(r.unitPrice) }}</span>
          <span v-if="!inventoryMode" class="bc-total"><em>Total</em> {{ num(r.totalPrice) }}</span>
        </div>
      </button>
      <div v-if="!filtered.length" class="bc-empty">
        <span class="empty-mark">—</span>
        No {{ inventoryMode ? 'inventory items' : 'BOM records' }} match the current view.
      </div>
    </div>

    <Modal
      v-if="panel"
      :title="
        isEditing
          ? `${inventoryMode ? 'Edit Inventory' : 'Edit BOM'} — ${panel.deviceName || ''}`
          : 'Add new item'
      "
      wide
      @close="panel = null"
    >
      <BomGlobalForm
        :record="isEditing ? panel : null"
        :target="isEditing && inventoryMode ? 'inventory' : 'bom'"
        :submitting="saving"
        @submit="onSave"
        @cancel="panel = null"
      />
    </Modal>

    <Modal
      v-if="detailCard"
      :title="detailCard.deviceName || 'Device details'"
      @close="detailCard = null"
    >
      <div class="device-card">
        <div class="dc-row">
          <span class="dc-label">Device name</span>
          <strong>{{ detailCard.deviceName || '—' }}</strong>
        </div>
        <div class="dc-row">
          <span class="dc-label">Version</span>
          <span>{{ detailCard.version || '—' }}</span>
        </div>
        <div class="dc-row">
          <span class="dc-label">Price / unit</span>
          <span class="dc-price">{{ num(detailCard.unitPrice) }}</span>
        </div>
        <div class="dc-row">
          <span class="dc-label">Supplier</span>
          <span>{{ detailCard.supplier || '—' }}</span>
        </div>
        <div class="dc-spec">
          <span class="dc-label">Spec</span>
          <div class="dc-spec-panel">{{ detailCard.spec || '—' }}</div>
        </div>
      </div>
    </Modal>

    <BomListPicker
      v-if="pickerList"
      :list="pickerList === 'new' ? null : pickerList"
      @close="pickerList = null"
      @saved="onPickerSaved"
      @request-pdf-export="(ctx) => (docExportCtx = ctx)"
    />

    <BomListsManager
      v-if="listsManagerOpen"
      @close="listsManagerOpen = false"
      @open-list="onManagerOpenList"
      @request-pdf-export="(ctx) => (docExportCtx = ctx)"
    />

    <BomExportDocsModal
      v-if="docExportCtx"
      :project="docExportCtx.project"
      :list-name="docExportCtx.listName"
      :rows="docExportCtx.rows"
      @close="docExportCtx = null"
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

/* Desktop only (bound off the same `isMobile` matchMedia that drives the grid's
   domLayout, so CSS and JS can never disagree): fill the viewport minus .main's
   28px top+bottom padding so the page never scrolls — the grid scrolls its rows
   internally instead, keeping the masthead, filter panel and column header
   locked in place. On mobile the class is absent, so the view falls back to
   natural flow and the grid's autoHeight page-scroll. */
.register.is-desktop {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}
.register.is-desktop .masthead,
.register.is-desktop .filters,
.register.is-desktop .byline { flex-shrink: 0; }

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
  font-size: clamp(20px, 5vw, 30px);
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
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  margin: 4px 0 2px;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 9px;
  flex: 1 1 240px;
  max-width: 400px;
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
.active { flex-basis: 100%; }
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

/* INVENTORY toggle — sits with the filter selects; glows while the grid shows
   the inventory catalogue instead of BOM records. */
.inv-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-end;
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-dim);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  cursor: pointer;
  transition: color .15s, border-color .15s, background-color .15s, box-shadow .15s;
}
.inv-toggle:hover { color: var(--accent); border-color: var(--accent); }
/* State class is `is-on`, not `active` — this component already uses `.active`
   for the active-filter chips row (flex-basis: 100%), which must not hit the
   toggle. */
.inv-toggle.is-on {
  color: var(--accent);
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  box-shadow: 0 0 14px color-mix(in srgb, var(--accent) 40%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, .12);
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

@media (max-width: 640px) {
  .filters { flex-direction: column; align-items: stretch; gap: 8px; }
  .search-box { flex: 0 0 auto; width: 100%; max-width: none; min-height: 38px; }
  .selects {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    width: 100%;
  }
  .selects label { gap: 3px; }
  .selects select { min-width: 0; width: 100%; height: 36px; font-size: 13px; }
  .active { flex: 0 0 auto; gap: 6px; }
  .active-chip { font-size: 11px; padding: 4px 8px; min-height: 26px; }
  .inv-toggle { width: 100%; justify-content: center; height: 38px; }
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

/* ---- Mobile card list (replaces the grid ≤760px) ---- */
.card-list { display: flex; flex-direction: column; gap: 10px; }
.bom-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 14px;
  text-align: left;
  font: inherit;
  color: var(--text);
  cursor: pointer;
}
.bom-card:active { transform: translateY(1px); }
.bc-top { display: flex; align-items: center; gap: 9px; }
.bc-folio {
  font-size: 11px; font-weight: 700;
  color: color-mix(in srgb, var(--text-dim) 70%, transparent);
  flex-shrink: 0;
}
.bc-name {
  font-family: var(--serif);
  font-weight: 600; font-size: 15px; line-height: 1.25;
  min-width: 0; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.bc-actions { display: flex; gap: 6px; flex-shrink: 0; }
.bc-actions .mini { width: 34px; height: 34px; }
.bc-actions .danger:hover { color: var(--danger); border-color: var(--danger); }
.bc-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.bc-chip {
  padding: 3px 9px; font-size: 11px; font-weight: 600;
  color: var(--text-dim);
}
.bc-figures {
  display: flex; flex-wrap: wrap; gap: 4px 16px;
  font-size: 13px; font-variant-numeric: tabular-nums;
}
.bc-figures em { font-style: normal; color: var(--text-dim); font-size: 11px; margin-right: 3px; }
.bc-total { font-weight: 700; }
.bc-empty {
  text-align: center; color: var(--text-dim);
  padding: 40px 12px; font-family: var(--serif); font-style: italic; font-size: 15px;
}
.bc-empty .empty-mark { display: block; font-size: 22px; color: var(--border); margin-bottom: 6px; }

/* Desktop: the ledger takes the remaining column height; min-height:0 lets the
   flex item shrink so the grid (not the page) provides the scroll. */
.register.is-desktop .ledger {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.register.is-desktop .grid { height: 100%; }

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

/* Rows open the details card on click. */
:deep(.ag-row) { cursor: pointer; }

/* --- Device details card (row-click quick view) --- */
.device-card { display: grid; gap: 14px; }
.dc-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  align-items: baseline;
  gap: 12px;
  font-size: 14px;
}
.dc-label {
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .05em;
  text-transform: uppercase;
}
.dc-price {
  font-weight: 700;
  color: var(--accent-dim);
  font-variant-numeric: tabular-nums;
}
.dc-spec { display: grid; gap: 6px; }
.dc-spec-panel {
  resize: vertical; /* user-adjustable height via the corner drag handle */
  overflow: auto;
  min-height: 84px;
  max-height: 60vh;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-sunken, var(--bg));
  white-space: pre-wrap;
  font-size: 13px;
  color: var(--text);
}
</style>

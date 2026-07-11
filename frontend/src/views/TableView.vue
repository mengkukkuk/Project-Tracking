<script setup>
import { ref, shallowRef, computed, h, defineComponent, onUnmounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { ModuleRegistry, AllCommunityModule, themeMaterial } from 'ag-grid-community'
import { useProjectsStore, taskProgress } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import StatusBadge from '@/components/StatusBadge.vue'
import PriorityBadge from '@/components/PriorityBadge.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'
import ExportImportMenu from '@/components/ExportImportMenu.vue'
import { useUiStore } from '@/stores/ui'
import {
  exportProjectsExcel,
  exportProjectsPdf,
  exportProjectsCsv,
} from '@/utils/recordExport'

ModuleRegistry.registerModules([AllCommunityModule])

const store = useProjectsStore()
const ui = useUiStore()
const { baht, date } = useFormat()

const density = ref('comfortable')
const gridApi = shallowRef(null)

// Below 760px (App.vue's mobile-shell breakpoint) the wide ag-grid is unusable,
// so swap it for a stacked card list. Mirrors BomGlobalView's matchMedia guard.
const mq = window.matchMedia('(max-width: 760px)')
const isMobile = ref(mq.matches)
const onMq = (e) => { isMobile.value = e.matches }
mq.addEventListener('change', onMq)
onUnmounted(() => mq.removeEventListener('change', onMq))

// Card list mirrors the grid's default due-date-ascending sort.
const mobileRows = computed(() =>
  [...store.projects].sort((a, b) => String(a.dueDate || '').localeCompare(String(b.dueDate || ''))),
)

const today = new Date()
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  .toUpperCase()

// Theming API — every colour is a live reference into this app's own CSS custom
// properties (see assets/main.css), so light/dark mode and the accent colour
// drive the grid with no second source of truth. No ag-grid CSS import needed.
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

const rowHeight = computed(() => (density.value === 'compact' ? 34 : 46))
const headerHeight = computed(() => (density.value === 'compact' ? 34 : 40))

// Thin Vue wrappers so the existing badge/progress components can be reused
// as ag-grid cellRenderers (each receives `params` with `.value` / `.data`).
const ProjectCell = defineComponent({
  props: ['params'],
  render() { return h('strong', { class: 'project-cell' }, this.params.value) },
})
const PriorityCell = defineComponent({
  props: ['params'],
  render() {
    return h('span', { class: 'grid-cell-center' }, [h(PriorityBadge, { priority: this.params.value })])
  },
})
const StatusCell = defineComponent({
  props: ['params'],
  render() {
    return h('span', { class: 'grid-cell-center' }, [h(StatusBadge, { status: this.params.value })])
  },
})
const ProgressCell = defineComponent({
  props: ['params'],
  render() { return h(ProgressBar, { value: this.params.value, showLabel: true }) },
})

const defaultColDef = {
  sortable: true,
  resizable: true,
  suppressMovable: true,
}

const columnDefs = computed(() => [
  {
    colId: 'folio',
    headerName: '№',
    width: 64,
    pinned: 'left',
    sortable: false,
    resizable: false,
    valueGetter: (p) => p.node.rowIndex + 1,
    valueFormatter: (p) => String(p.value).padStart(2, '0'),
    cellClass: 'folio-col mono',
    headerClass: 'folio-col',
  },
  { field: 'domain', headerName: 'Domain', minWidth: 120 },
  {
    field: 'name',
    headerName: 'Project',
    pinned: 'left',
    flex: 1.6,
    minWidth: 190,
    cellRenderer: ProjectCell,
  },
  { field: 'pm', headerName: 'PM', minWidth: 110 },
  { field: 'customer', headerName: 'Customer', minWidth: 150 },
  {
    field: 'value',
    headerName: 'Value',
    minWidth: 100,
    cellClass: 'num',
    headerClass: 'num',
    valueFormatter: (p) => baht(p.value),
  },
  { field: 'priority', headerName: 'Priority', minWidth: 110, cellRenderer: PriorityCell },
  { field: 'status', headerName: 'Status', minWidth: 150, cellRenderer: StatusCell },
  {
    colId: 'progress',
    headerName: 'Progress',
    minWidth: 170,
    flex: 1,
    valueGetter: (p) => taskProgress(p.data),
    cellRenderer: ProgressCell,
  },
  {
    field: 'dueDate',
    headerName: 'Due date',
    minWidth: 110,
    sort: 'asc',
    valueFormatter: (p) => date(p.value),
  },
])

const rowData = computed(() => store.projects)
const shownCount = computed(() => store.projects.length)

const noRowsTemplate =
  '<div class="empty"><span class="empty-mark">—</span>No entries match the current view.</div>'

function onGridReady(e) {
  gridApi.value = e.api
}

function onRowClicked(e) {
  store.openDetail(e.data.id)
}

// Export the currently sorted/filtered order, mirroring what's on screen.
function sortedRows() {
  const rows = []
  gridApi.value?.forEachNodeAfterFilterAndSort((n) => rows.push(n.data))
  return rows
}

async function doExport(format) {
  const rows = sortedRows()
  if (!rows.length) return
  try {
    if (format === 'excel') await exportProjectsExcel(rows)
    else if (format === 'pdf') exportProjectsPdf(rows)
    else exportProjectsCsv(rows)
    ui.success(
      `Exported ${rows.length} project(s) to ${format === 'excel' ? 'Excel' : format.toUpperCase()}`,
    )
  } catch (e) {
    ui.error(e.message)
  }
}
</script>

<template>
  <div class="view register">
    <!-- Editorial masthead ------------------------------------------------ -->
    <header class="masthead">
      <div class="dateline mono">
        <span>Project&nbsp;Tracking</span>
        <span class="sep">·</span>
        <span>Total projects : {{ store.projects.length }}</span>
        <span class="sep">·</span>
        <span>{{ today }}</span>
      </div>

      <div class="masthead-row">
        <h1 class="masthead-title">Tracking&nbsp;Table</h1>

        <div class="actions">
          <div class="segmented" aria-label="Table density">
            <button type="button" :class="{ active: density === 'comfortable' }" @click="density = 'comfortable'">Comfort</button>
            <button type="button" :class="{ active: density === 'compact' }" @click="density = 'compact'">Compact</button>
          </div>
          <ExportImportMenu
            :formats="['excel', 'pdf', 'csv']"
            :rows="shownCount"
            @export="doExport"
          />
        </div>
      </div>

      <p class="masthead-sub">
        แสดงรายการ Project ทั้งหมด || Export to excel/pdf
      </p>
    </header>

    <ProjectFilters compact />

    <div class="byline mono">
      <span class="folio">{{ String(shownCount).padStart(2, '0') }}</span>
      entr{{ shownCount === 1 ? 'y' : 'ies' }} in view
      <span class="of">of {{ store.projects.length }} on record</span>
    </div>

    <!-- The ledger --------------------------------------------------------- -->
    <div v-if="!isMobile" class="ledger" :class="density" :style="{ '--row-h': rowHeight + 'px' }">
      <AgGridVue
        class="grid"
        :theme="gridTheme"
        :columnDefs="columnDefs"
        :rowData="rowData"
        :defaultColDef="defaultColDef"
        :rowHeight="rowHeight"
        :headerHeight="headerHeight"
        domLayout="autoHeight"
        :suppressCellFocus="true"
        :overlayNoRowsTemplate="noRowsTemplate"
        @grid-ready="onGridReady"
        @row-clicked="onRowClicked"
      />
    </div>

    <!-- Mobile: stacked cards instead of the wide grid --------------------- -->
    <div v-else class="card-list">
      <button
        v-for="(p, i) in mobileRows"
        :key="p.id"
        type="button"
        class="proj-card card"
        @click="store.openDetail(p.id)"
      >
        <div class="pc-top">
          <span class="pc-folio mono">{{ String(i + 1).padStart(2, '0') }}</span>
          <strong class="pc-name">{{ p.name }}</strong>
        </div>
        <div class="pc-badges">
          <StatusBadge :status="p.status" />
          <PriorityBadge :priority="p.priority" />
        </div>
        <div class="pc-meta">
          <span>{{ p.pm || 'No PM' }} · {{ p.customer || 'No customer' }}</span>
        </div>
        <div class="pc-figures">
          <span class="pc-value mono">{{ baht(p.value) }}</span>
          <span class="pc-due mono">{{ date(p.dueDate) }}</span>
        </div>
        <ProgressBar :value="taskProgress(p)" showLabel />
      </button>
      <div v-if="!mobileRows.length" class="pc-empty">
        <span class="empty-mark">—</span>No entries match the current view.
      </div>
    </div>
  </div>
</template>

<style scoped>
.register {
  /* Project uses a single typeface (IBM Plex Sans Thai via --font). The
     masthead/title weight + size carry the editorial character instead. */
  --serif: var(--font);
  --rule: color-mix(in srgb, var(--text) 78%, transparent);
}

/* ---- Masthead ---- */
.masthead {
  border-top: 2px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 12px 0 16px;
  margin-bottom: 18px;
  animation: mast-in .5s cubic-bezier(.2, .7, .2, 1) both;
}
@keyframes mast-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: none; }
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
  font-optical-sizing: auto;
  font-weight: 500;
  font-size: clamp(34px, 5vw, 52px);
  line-height: .98;
  letter-spacing: -.015em;
  color: var(--text);
  margin: 0;
}
.masthead-title em {
  font-style: italic;
  font-weight: 600;
  color: var(--accent-dim);
}
.masthead-sub {
  font-family: var(--serif);
  font-size: 15px;
  font-style: italic;
  color: var(--text-dim);
  margin-top: 10px;
  max-width: 60ch;
}

.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding-bottom: 4px; }
.segmented {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.segmented button {
  border: 0;
  background: transparent;
  color: var(--text-dim);
  border-radius: 6px;
  min-height: 28px;
  padding: 0 11px;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color .12s, background .12s, box-shadow .12s;
}
.segmented button:hover { color: var(--text); }
.segmented button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.segmented button.active {
  background: var(--accent);
  color: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .2), 0 1px 3px rgba(15, 23, 42, .12);
}

/* ---- Byline / folio line ---- */
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
.byline .folio {
  font-size: 13px;
  color: var(--accent-dim);
  font-weight: 700;
}
.byline .of { color: var(--border); }
.byline .of { color: color-mix(in srgb, var(--text-dim) 70%, transparent); }

/* ---- The ledger (ag-grid) ---- */
.ledger {
  border-top: 1.5px solid var(--rule);
  border-bottom: 1.5px solid var(--rule);
}
.grid { width: 100%; }

/* ag-grid renders its own internal DOM imperatively, so these rules reach
   into it via :deep() rather than styling this component's own template. */
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
:deep(.ag-row) { cursor: pointer; }
/* ag-grid's cell content is a flex item that stretches to the row's full
   height by default — badges/pills have no intrinsic height, so they'd
   otherwise balloon to fill it. Auto margins win over any ancestor's
   align-items, so this centers them at their natural size regardless of
   ag-grid's internal wrapper structure. */
:deep(.grid-cell-center) {
  display: inline-flex;
  align-items: center;
  margin-top: auto;
  margin-bottom: auto;
  max-width: 100%;
}
/* Pin the priority/status pills to a fixed height (50% of the current row
   height, from --row-h set below) instead of letting them stretch to fill
   the cell — kept scoped to this view via :deep() so the shared
   PriorityBadge/StatusBadge components stay untouched for other views. */
:deep(.pri),
:deep(.badge) {
  box-sizing: border-box;
  height: calc(var(--row-h) * 0.5);
  display: inline-flex;
  align-items: center;
  padding-top: 0;
  padding-bottom: 0;
  line-height: 1;
}
:deep(.project-cell) {
  font-family: var(--serif);
  font-weight: 600;
  font-size: 15px;
  letter-spacing: -.005em;
  line-height: 1.25;
}
:deep(.empty) {
  text-align: center;
  color: var(--text-dim);
  padding: 48px;
  font-family: var(--serif);
  font-style: italic;
  font-size: 15px;
}
:deep(.empty-mark) { display: block; font-size: 22px; color: var(--border); margin-bottom: 6px; }

/* Density: header/row height are bound reactively via props; compact only
   trims horizontal breathing room. */
.compact :deep(.ag-cell),
.compact :deep(.ag-header-cell) { padding-left: 10px; padding-right: 10px; }

@media (max-width: 720px) {
  .masthead-row { align-items: stretch; }
  .masthead-sub { font-size: 14px; }
  .masthead-title { font-size: clamp(28px, 9vw, 40px); }
  .dateline { gap: 6px; font-size: 9.5px; flex-wrap: wrap; }
  .actions { width: 100%; justify-content: space-between; }
  .empty { padding: 32px 12px; }
}

/* ---- Mobile card list (replaces the grid ≤760px) ---- */
.card-list { display: flex; flex-direction: column; gap: 10px; }
.proj-card {
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
.proj-card:active { transform: translateY(1px); }
.pc-top { display: flex; align-items: baseline; gap: 9px; }
.pc-folio {
  font-size: 11px; font-weight: 700;
  color: color-mix(in srgb, var(--text-dim) 70%, transparent);
  flex-shrink: 0;
}
.pc-name {
  font-family: var(--serif);
  font-weight: 600; font-size: 16px; line-height: 1.25;
  letter-spacing: -.005em;
  min-width: 0;
}
.pc-badges { display: flex; flex-wrap: wrap; gap: 6px; }
.pc-meta { color: var(--text-dim); font-size: 12px; }
.pc-figures {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px; font-size: 13px;
}
.pc-value { font-weight: 700; color: var(--text); }
.pc-due { color: var(--text-dim); }
.pc-empty {
  text-align: center; color: var(--text-dim);
  padding: 40px 12px; font-family: var(--serif); font-style: italic; font-size: 15px;
}
.pc-empty .empty-mark { display: block; font-size: 22px; color: var(--border); margin-bottom: 6px; }
</style>

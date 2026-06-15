<script setup>
import { ref, h, computed } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  FlexRender,
} from '@tanstack/vue-table'
import { useProjectsStore, taskProgress } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import StatusSelect from '@/components/StatusSelect.vue'
import PriorityBadge from '@/components/PriorityBadge.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'
import AppIcon from '@/components/AppIcon.vue'

const store = useProjectsStore()
const { baht, date } = useFormat()

const sorting = ref([{ id: 'dueDate', desc: false }])
const density = ref('comfortable')

const today = new Date()
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  .toUpperCase()

// Right-aligned, figure-style columns get the ledger numeral treatment.
const NUM_COLS = new Set(['value'])

const columns = [
  { accessorKey: 'domain', header: 'Domain' },
  {
    accessorKey: 'name',
    header: 'Project',
    cell: (i) => h('strong', { class: 'project-cell' }, i.getValue()),
  },
  { accessorKey: 'pm', header: 'PM' },
  { accessorKey: 'customer', header: 'Customer' },
  { accessorKey: 'value', header: 'Value', cell: (i) => baht(i.getValue()) },
  { accessorKey: 'priority', header: 'Priority', cell: (i) => h(PriorityBadge, { priority: i.getValue() }) },
  { accessorKey: 'status', header: 'Status', cell: (i) => h(StatusSelect, { id: i.row.original.id, status: i.getValue() }) },
  {
    id: 'progress',
    accessorFn: (row) => taskProgress(row),
    header: 'Progress',
    cell: (i) => h(ProgressBar, { value: i.getValue(), showLabel: true }),
  },
  { accessorKey: 'dueDate', header: 'Due date', cell: (i) => date(i.getValue()) },
]

const table = useVueTable({
  get data() { return store.projects },
  columns,
  state: {
    get sorting() { return sorting.value },
  },
  onSortingChange: (u) => (sorting.value = typeof u === 'function' ? u(sorting.value) : u),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const shownCount = computed(() => table.getSortedRowModel().rows.length)

function exportCsv() {
  const rows = table.getSortedRowModel().rows
  const headers = ['Domain', 'Name', 'PM', 'Customer', 'Value', 'Priority', 'Status', 'Progress', 'FiscalYear', 'DueDate']
  const lines = rows.map((r) => {
    const p = r.original
    return [p.domain, p.name, p.pm, p.customer, p.value, p.priority, p.status, taskProgress(p), p.fiscalYear, p.dueDate]
      .map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`)
      .join(',')
  })
  const blob = new Blob(['\uFEFF' + headers.join(',') + '\n' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `projects-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
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
        <h1 class="masthead-title"> <em>Tracking&nbsp;Table</em> </h1>

        <div class="actions">
          <div class="segmented" aria-label="Table density">
            <button type="button" :class="{ active: density === 'comfortable' }" @click="density = 'comfortable'">Comfort</button>
            <button type="button" :class="{ active: density === 'compact' }" @click="density = 'compact'">Compact</button>
          </div>
          <button class="btn ghost" @click="exportCsv">
            <AppIcon name="download" :size="16" />
            Export CSV
          </button>
        </div>
      </div>

      <p class="masthead-sub">
        Lists of the current projects pipeline — sort, filter, inspect, and export.
      </p>
    </header>

    <ProjectFilters compact />

    <div class="byline mono">
      <span class="folio">{{ String(shownCount).padStart(2, '0') }}</span>
      entr{{ shownCount === 1 ? 'y' : 'ies' }} in view
      <span class="of">of {{ store.projects.length }} on record</span>
    </div>

    <!-- The ledger --------------------------------------------------------- -->
    <div class="ledger" :class="density">
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
                <span class="sort-ind" :class="{ on: header.column.getIsSorted() }">
                  {{ header.column.getIsSorted() === 'asc' ? '▲' : header.column.getIsSorted() === 'desc' ? '▼' : '◆' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in table.getRowModel().rows"
            :key="row.id"
            class="row"
            @click="store.openDetail(row.original.id)"
          >
            <td class="folio-col mono">{{ String(idx + 1).padStart(2, '0') }}</td>
            <td
              v-for="cell in row.getVisibleCells()"
              :key="cell.id"
              :class="{ num: NUM_COLS.has(cell.column.id) }"
            >
              <FlexRender :render="cell.column.columnDef.cell ?? cell.column.columnDef.accessorKey" :props="cell.getContext()" />
            </td>
          </tr>
          <tr v-if="!table.getRowModel().rows.length">
            <td :colspan="columns.length + 1" class="empty">
              <span class="empty-mark">—</span>
              No entries match the current view.
            </td>
          </tr>
        </tbody>
      </table>
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
  transition: color .12s, background .12s;
}
.segmented button.active { background: var(--accent); color: #fff; }

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

/* ---- The ledger table ---- */
.ledger {
  overflow-x: auto;
  border-top: 1.5px solid var(--rule);
  border-bottom: 1.5px solid var(--rule);
}
table { width: 100%; border-collapse: collapse; min-width: 880px; }

thead th {
  text-align: left;
  padding: 11px 14px;
  font-family: var(--font);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--text-dim);
  background: transparent;
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

.sort-ind {
  font-size: 8px;
  opacity: 0;
  color: var(--accent);
  transition: opacity .12s, transform .12s;
}
th.sortable:hover .sort-ind { opacity: .35; }
.sort-ind.on { opacity: 1; }

.folio-col {
  width: 1%;
  text-align: right;
  padding-right: 10px !important;
  color: color-mix(in srgb, var(--text-dim) 65%, transparent);
  font-size: 11px;
}
thead .folio-col { font-size: 11px; }

tbody td {
  padding: 13px 14px;
  font-size: 13px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
td.num {
  font-family: var(--font);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  letter-spacing: -.01em;
}

.compact tbody td { padding: 8px 12px; }
.compact thead th { padding: 8px 12px; }

.row {
  cursor: pointer;
  position: relative;
  transition: background .12s;
}
.row td:first-child { box-shadow: inset 0 0 0 0 var(--accent); transition: box-shadow .12s; }
.row:hover { background: color-mix(in srgb, var(--accent) 5%, var(--surface)); }
.row:hover td:first-child { box-shadow: inset 3px 0 0 0 var(--accent); }
.row:hover .folio-col { color: var(--accent-dim); }
tbody tr:last-child td { border-bottom: none; }

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
  font-size: 15px;
  letter-spacing: -.005em;
  line-height: 1.25;
}

@media (max-width: 720px) {
  .masthead-row { align-items: stretch; }
  .masthead-sub { font-size: 14px; }
  .masthead-title { font-size: clamp(28px, 9vw, 40px); }
  .dateline { gap: 6px; font-size: 9.5px; flex-wrap: wrap; }
  .actions { width: 100%; justify-content: space-between; }

  /* Stack each table row as an editorial card */
  .ledger {
    border: 0;
    overflow: visible;
  }
  table { min-width: 0; display: block; }
  thead { display: none; }
  tbody, tr { display: block; }
  .row {
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-areas:
      "folio name      status"
      "folio meta      value"
      "tags  tags      tags";
    column-gap: 12px;
    row-gap: 6px;
    align-items: center;
    padding: 14px 12px;
    margin: 0 -2px;
    border-bottom: 1px solid var(--border);
  }
  .row:hover { background: transparent; }
  .row:hover td:first-child { box-shadow: none; }
  .row td { padding: 0; border: 0; font-size: 13px; }
  .row td:nth-child(1) { grid-area: folio; align-self: start; }
  .row td:nth-child(3) { grid-area: name; font-size: 16px; }
  .row td:nth-child(8) { grid-area: status; justify-self: end; }
  .row td:nth-child(6) { grid-area: value; justify-self: end; font-weight: 700; }
  /* meta line: domain · pm · customer · due  */
  .row td:nth-child(2),
  .row td:nth-child(4),
  .row td:nth-child(5),
  .row td:nth-child(10) {
    grid-area: meta;
    display: inline;
    color: var(--text-dim);
    font-size: 12px;
  }
  .row td:nth-child(2)::after,
  .row td:nth-child(4)::after,
  .row td:nth-child(5)::after {
    content: ' · ';
    color: var(--border);
  }
  .row td:nth-child(7) { display: none; } /* priority badge — implied by row */
  .row td:nth-child(9) {                 /* progress bar full-width */
    grid-area: tags;
    display: block;
  }
  :deep(.project-cell) { font-size: 16px; }
  .empty { padding: 32px 12px; }
}
</style>

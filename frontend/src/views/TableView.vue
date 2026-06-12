<script setup>
import { ref, h } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  FlexRender,
} from '@tanstack/vue-table'
import { useProjectsStore } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import StatusBadge from '@/components/StatusBadge.vue'
import PriorityBadge from '@/components/PriorityBadge.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'
import AppIcon from '@/components/AppIcon.vue'

const store = useProjectsStore()
const { baht, date } = useFormat()

const sorting = ref([{ id: 'dueDate', desc: false }])
const density = ref('comfortable')

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
  { accessorKey: 'status', header: 'Status', cell: (i) => h(StatusBadge, { status: i.getValue() }) },
  {
    accessorKey: 'progress',
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

function exportCsv() {
  const rows = table.getSortedRowModel().rows
  const headers = ['Domain', 'Name', 'PM', 'Customer', 'Value', 'Priority', 'Status', 'Progress', 'FiscalYear', 'DueDate']
  const lines = rows.map((r) => {
    const p = r.original
    return [p.domain, p.name, p.pm, p.customer, p.value, p.priority, p.status, p.progress, p.fiscalYear, p.dueDate]
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
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Project register</div>
        <h1 class="page-title">Table</h1>
        <p class="page-subtitle">Sort, filter, inspect, and export the current project register.</p>
      </div>
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
    </header>

    <ProjectFilters compact />

    <div class="meta-row muted">
      Showing {{ table.getSortedRowModel().rows.length }} of {{ store.projects.length }} projects
    </div>

    <div class="table-wrap card" :class="density">
      <table>
        <thead>
          <tr v-for="hg in table.getHeaderGroups()" :key="hg.id">
            <th
              v-for="header in hg.headers"
              :key="header.id"
              :class="{ sortable: header.column.getCanSort() }"
              @click="header.column.getToggleSortingHandler()?.($event)"
            >
              <FlexRender :render="header.column.columnDef.header" :props="header.getContext()" />
              <span v-if="header.column.getIsSorted()" class="sort-ind">
                {{ header.column.getIsSorted() === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in table.getRowModel().rows" :key="row.id" class="row" @click="store.openDetail(row.original.id)">
            <td v-for="cell in row.getVisibleCells()" :key="cell.id">
              <FlexRender :render="cell.column.columnDef.cell ?? cell.column.columnDef.accessorKey" :props="cell.getContext()" />
            </td>
          </tr>
          <tr v-if="!table.getRowModel().rows.length">
            <td :colspan="columns.length" class="empty">No projects match the current view.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
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
  padding: 0 9px;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.segmented button.active {
  background: var(--accent);
  color: #fff;
}
.meta-row { font-size: 12px; margin-bottom: 12px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 820px; }
th { text-align: left; padding: 12px 14px; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-dim); background: var(--bg-sunken); border-bottom: 1px solid var(--border); user-select: none; white-space: nowrap; }
th.sortable { cursor: pointer; }
th.sortable:hover { color: var(--text); }
.sort-ind { margin-left: 4px; font-size: 9px; }
td { padding: 11px 14px; font-size: 13px; color: var(--text); border-bottom: 1px solid var(--border); }
.compact td { padding: 7px 12px; }
.compact th { padding: 9px 12px; }
.row { cursor: pointer; transition: background .1s; }
.row:hover { background: var(--bg-sunken); }
tbody tr:last-child td { border-bottom: none; }
.empty { text-align: center; color: var(--text-dim); padding: 40px; }
:deep(.project-cell) {
  font-weight: 700;
}
</style>

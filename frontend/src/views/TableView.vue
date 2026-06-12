<script setup>
import { ref, h } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  FlexRender,
} from '@tanstack/vue-table'
import { useProjectsStore, STAGES } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import StatusBadge from '@/components/StatusBadge.vue'
import PriorityBadge from '@/components/PriorityBadge.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const store = useProjectsStore()
const { baht, date } = useFormat()

const globalFilter = ref('')
const sorting = ref([{ id: 'updatedAt', desc: true }])

const DOMAINS = ['Vision Sensor', 'Robot', 'PLC', 'IoT', 'AI']

const columns = [
  { accessorKey: 'domain', header: 'กลุ่มงาน' },
  { accessorKey: 'name', header: 'โครงการ' },
  { accessorKey: 'pm', header: 'PM' },
  { accessorKey: 'customer', header: 'ลูกค้า' },
  { accessorKey: 'value', header: 'มูลค่า', cell: (i) => baht(i.getValue()) },
  { accessorKey: 'priority', header: 'ความสำคัญ', cell: (i) => h(PriorityBadge, { priority: i.getValue() }) },
  { accessorKey: 'status', header: 'สถานะ', cell: (i) => h(StatusBadge, { status: i.getValue() }) },
  {
    accessorKey: 'progress',
    header: 'คืบหน้า',
    cell: (i) => h(ProgressBar, { value: i.getValue(), showLabel: true }),
  },
  { accessorKey: 'dueDate', header: 'กำหนดส่ง', cell: (i) => date(i.getValue()) },
]

const table = useVueTable({
  get data() { return store.projects },
  columns,
  state: {
    get sorting() { return sorting.value },
    get globalFilter() { return globalFilter.value },
  },
  onSortingChange: (u) => (sorting.value = typeof u === 'function' ? u(sorting.value) : u),
  onGlobalFilterChange: (v) => (globalFilter.value = v),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
})

function exportCsv() {
  const rows = table.getFilteredRowModel().rows
  const headers = ['Domain', 'Name', 'PM', 'Customer', 'Value', 'Priority', 'Status', 'Progress', 'FiscalYear', 'DueDate']
  const lines = rows.map((r) => {
    const p = r.original
    return [p.domain, p.name, p.pm, p.customer, p.value, p.priority, p.status, p.progress, p.fiscalYear, p.dueDate]
      .map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`)
      .join(',')
  })
  const blob = new Blob(['﻿' + headers.join(',') + '\n' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
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
    <div class="toolbar">
      <h1 class="page-title">ตารางโครงการ</h1>
      <div class="actions">
        <input v-model="globalFilter" class="input search" placeholder="ค้นหาในตาราง..." />
        <select class="select sm" :value="store.filters.status" @change="store.setFilter({ status: $event.target.value })">
          <option value="">ทุกสถานะ</option>
          <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
        </select>
        <select class="select sm" :value="store.filters.domain" @change="store.setFilter({ domain: $event.target.value })">
          <option value="">ทุกกลุ่มงาน</option>
          <option v-for="d in DOMAINS" :key="d" :value="d">{{ d }}</option>
        </select>
        <button class="btn ghost" @click="exportCsv">⬇ Export CSV</button>
      </div>
    </div>

    <div class="meta-row muted">แสดง {{ table.getFilteredRowModel().rows.length }} จาก {{ store.projects.length }} โครงการ</div>

    <div class="table-wrap card">
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
            <td :colspan="columns.length" class="empty">ไม่พบโครงการ</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 12px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.search { width: 200px; }
.select.sm { width: auto; padding: 7px 10px; font-size: 13px; }
.meta-row { font-size: 12px; margin-bottom: 12px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 760px; }
th { text-align: left; padding: 12px 14px; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-dim); background: var(--bg-sunken); border-bottom: 1px solid var(--border); user-select: none; white-space: nowrap; }
th.sortable { cursor: pointer; }
th.sortable:hover { color: var(--text); }
.sort-ind { margin-left: 4px; font-size: 9px; }
td { padding: 11px 14px; font-size: 13px; color: var(--text); border-bottom: 1px solid var(--border); }
.row { cursor: pointer; transition: background .1s; }
.row:hover { background: var(--bg-sunken); }
tbody tr:last-child td { border-bottom: none; }
.empty { text-align: center; color: var(--text-dim); padding: 40px; }
</style>

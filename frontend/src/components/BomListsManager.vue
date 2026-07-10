<script setup>
// Browse saved BOM lists. Per-row actions: Open (re-launches the picker in
// edit mode), Export Excel, Export PDF, Delete. Per the plan, any authed user
// can view all lists; only the owner or an admin can delete/edit (the backend
// enforces this — non-owner deletes surface as a 403 toast here).
import { ref, onMounted, computed } from 'vue'
import { useBomListsStore } from '@/stores/bomLists'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import { exportBomListExcel } from '@/utils/recordExport'
import { api } from '@/api'
import Modal from './Modal.vue'

const emit = defineEmits(['close', 'open-list', 'request-pdf-export'])

const store = useBomListsStore()
const projectsStore = useProjectsStore()
const ui = useUiStore()
const { date } = useFormat()

const exportingId = ref(null)

const lists = computed(() => store.lists)

onMounted(() => {
  store.fetchAll().catch((e) => ui.error(e.message))
  if (!projectsStore.projects.length) {
    projectsStore.fetchAll().catch(() => {})
  }
})

function openList(lst) {
  emit('open-list', lst)
}

async function doExport(lst, format) {
  exportingId.value = `${lst.id}:${format}`
  try {
    // Detail endpoint enriches each item with projectName already.
    const detail = await api.getBomList(lst.id)
    const project = projectsStore.projects.find((p) => p.id === lst.projectId) || {
      id: lst.projectId,
      name: lst.projectName || '',
    }
    const rows = detail.items || []
    if (!rows.length) {
      ui.error('This list has no items to export.')
      return
    }
    if (format === 'excel') {
      await exportBomListExcel(project, lst.name, rows)
      ui.success(`Exported "${lst.name}" to Excel`)
      return
    }
    // PDF: hand off to the doc-picker modal (owned by BomGlobalView); it owns
    // the export + its own success/error toasts.
    emit('request-pdf-export', { project, listName: lst.name, rows })
  } catch (e) {
    ui.error(e.message)
  } finally {
    exportingId.value = null
  }
}

async function remove(lst) {
  if (!window.confirm(`Delete BOM list "${lst.name}"?`)) return
  try {
    await store.remove(lst.id)
    ui.success('BOM list deleted')
  } catch (e) {
    ui.error(e.message)
  }
}
</script>

<template>
  <Modal title="Saved BOM Lists" wide @close="emit('close')">
    <div class="ledger">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Project</th>
            <th class="num">Items</th>
            <th>Updated</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="store.loading">
            <td colspan="5" class="empty">Loading…</td>
          </tr>
          <tr v-for="lst in lists" :key="lst.id" class="row">
            <td><strong>{{ lst.name }}</strong></td>
            <td>{{ lst.projectName || '—' }}</td>
            <td class="num">{{ lst.itemCount }}</td>
            <td>{{ date(lst.updatedAt) }}</td>
            <td class="actions-col">
              <button class="mini" @click="openList(lst)">Open</button>
              <button
                class="mini"
                :disabled="exportingId === `${lst.id}:excel`"
                @click="doExport(lst, 'excel')"
              >
                Excel
              </button>
              <button
                class="mini"
                :disabled="exportingId === `${lst.id}:pdf`"
                @click="doExport(lst, 'pdf')"
              >
                PDF
              </button>
              <button class="mini danger" @click="remove(lst)">Delete</button>
            </td>
          </tr>
          <tr v-if="!store.loading && !lists.length">
            <td colspan="5" class="empty">
              <span class="empty-mark">—</span>
              No saved BOM lists yet. Use <strong>+ Create BOM List</strong> to make one.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <template #footer>
      <button type="button" class="btn ghost" @click="emit('close')">Close</button>
    </template>
  </Modal>
</template>

<style scoped>
.ledger { max-height: 60vh; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
table { width: 100%; border-collapse: collapse; }
thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface);
  text-align: left;
  padding: 9px 12px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
.actions-col { width: 1%; white-space: nowrap; text-align: right; }
tbody td {
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
tbody tr:last-child td { border-bottom: none; }
.row:hover { background: color-mix(in srgb, var(--accent) 5%, var(--surface)); }
.empty { text-align: center; padding: 32px; color: var(--text-dim); font-style: italic; }
.empty-mark { display: block; font-size: 20px; color: var(--border); margin-bottom: 4px; }

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
  margin-left: 4px;
  transition: color .1s, border-color .1s;
}
.mini:hover { color: var(--accent); border-color: var(--accent); }
.mini:disabled { opacity: .6; cursor: not-allowed; }
.mini.danger:hover { color: #c0392b; border-color: #c0392b; }
</style>

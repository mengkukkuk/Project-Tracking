<script setup>
import { computed, ref, watch } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import { RECORD_SCHEMAS } from '@/schemas/records'
import { exportRecordsExcel, exportRecordsPdf, parseRecordsExcel } from '@/utils/recordExport'
import AppIcon from './AppIcon.vue'
import Modal from './Modal.vue'
import RecordForm from './RecordForm.vue'
import ExportImportMenu from './ExportImportMenu.vue'
import ImportResultModal from './ImportResultModal.vue'

const props = defineProps({
  resource: { type: String, required: true },
})

const store = useProjectsStore()
const ui = useUiStore()
const { date } = useFormat()

const schema = computed(() => RECORD_SCHEMAS[props.resource])
const rows = computed(() => store.records[props.resource] || [])
const fieldMap = computed(() =>
  Object.fromEntries(schema.value.fields.map((f) => [f.key, f])),
)

const editing = ref(null) // record being edited, or {} for a new one
const submitting = ref(false)

// --- Export / Import ---
const importResult = ref(null) // { valid, errors, unmatched } from a parsed file
const importing = ref(false)

async function doExport(format) {
  if (!rows.value.length) return
  try {
    const name = store.current?.name || ''
    if (format === 'excel') await exportRecordsExcel(props.resource, rows.value, name)
    else exportRecordsPdf(props.resource, rows.value, name)
    ui.success(
      `Exported ${rows.value.length} ${schema.value.label} record(s) to ${format === 'excel' ? 'Excel' : 'PDF'}`,
    )
  } catch (e) {
    ui.error(e.message)
  }
}

async function onImportFile(file) {
  try {
    importResult.value = await parseRecordsExcel(props.resource, file)
  } catch (err) {
    ui.error(err.message)
  }
}

async function confirmImport() {
  const valid = importResult.value?.valid || []
  if (!valid.length) return
  importing.value = true
  try {
    for (const rec of valid) {
      await store.addRecord(props.resource, rec)
    }
    ui.success(`Imported ${valid.length} ${schema.value.label} record(s)`)
    importResult.value = null
  } catch (e) {
    ui.error(e.message)
  } finally {
    importing.value = false
  }
}

// Load whenever the active resource tab changes (and on first mount).
watch(
  () => props.resource,
  (r) => {
    if (store.current && !(r in store.records)) store.fetchRecords(r)
  },
  { immediate: true },
)

function openCreate() {
  editing.value = {}
}
function openEdit(row) {
  editing.value = row
}
function closeForm() {
  editing.value = null
}

async function submit(data) {
  submitting.value = true
  try {
    if (editing.value && editing.value.id) {
      await store.editRecord(props.resource, editing.value.id, data)
      ui.success('Record updated')
    } else {
      await store.addRecord(props.resource, data)
      ui.success('Record added')
    }
    closeForm()
  } catch (e) {
    ui.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function remove(row) {
  if (!confirm('Delete this record?')) return
  try {
    await store.removeRecord(props.resource, row.id)
  } catch (e) {
    ui.error(e.message)
  }
}

function display(row, key) {
  const f = fieldMap.value[key]
  const v = row[key]
  if (f?.type === 'checkbox') return v ? '✓' : '—'
  if (f?.type === 'date') return v ? date(v) : '—'
  if (f?.type === 'number') return v == null ? '—' : v.toLocaleString()
  return v || '—'
}
</script>

<template>
  <section class="rlist panel">
    <header class="rl-head">
      <h3 class="sec-title">{{ schema.label }} <span>{{ rows.length }}</span></h3>
      <div class="rl-actions">
        <ExportImportMenu
          :formats="['excel', 'pdf']"
          :rows="rows.length"
          import-enabled
          @export="doExport"
          @import-file="onImportFile"
        />
        <button class="btn sm" @click="openCreate">
          <AppIcon name="plus" :size="14" />
          Add
        </button>
      </div>
    </header>

    <div v-if="store.recordsLoading && !rows.length" class="empty">Loading...</div>

    <div v-else-if="rows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th v-for="c in schema.columns" :key="c">{{ fieldMap[c]?.label || c }}</th>
            <th class="actions-col" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td v-for="c in schema.columns" :key="c" :class="{ num: fieldMap[c]?.type === 'number' }">
              {{ display(row, c) }}
            </td>
            <td class="actions-col">
              <button class="del" title="Edit" @click="openEdit(row)">
                <AppIcon name="edit" :size="13" />
              </button>
              <button class="del" title="Delete" @click="remove(row)">
                <AppIcon name="trash" :size="13" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else class="empty">No {{ schema.label.toLowerCase() }} records yet.</p>

    <Modal
      v-if="editing"
      wide
      :title="`${editing.id ? 'Edit' : 'Add'} ${schema.label}`"
      @close="closeForm"
    >
      <RecordForm
        :resource="resource"
        :record="editing.id ? editing : null"
        :submitting="submitting"
        @submit="submit"
        @cancel="closeForm"
      />
    </Modal>

    <ImportResultModal
      v-if="importResult"
      :title="`Import ${schema.label}`"
      :result="importResult"
      :importing="importing"
      @close="importResult = null"
      @confirm="confirmImport"
    />
  </section>
</template>

<style scoped>
.rlist { display: grid; gap: 12px; }
.rl-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.rl-actions { display: flex; align-items: center; gap: 6px; }
.sec-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.sec-title span { color: var(--text-dim); }
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  white-space: nowrap;
}
th {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--text-dim);
  background: var(--bg-sunken);
}
tbody tr:last-child td { border-bottom: 0; }
td.num { text-align: center; font-variant-numeric: tabular-nums; }
.actions-col { width: 1%; text-align: right; }
td.actions-col { display: flex; gap: 4px; justify-content: flex-end; }
.del { display: grid; place-items: center; background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 3px; opacity: .6; }
.del:hover { opacity: 1; color: var(--accent); }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; padding: 8px 0; }
</style>

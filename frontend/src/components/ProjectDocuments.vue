<script setup>
import { computed, ref, watch } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import { api } from '@/api'
import AppIcon from './AppIcon.vue'
import Modal from './Modal.vue'

const DOC_TYPES = [
  ['quotation', 'Quotation'],
  ['tds', 'Technical Datasheet'],
  ['result', 'Result'],
]
const LABELS = Object.fromEntries(DOC_TYPES)

const store = useProjectsStore()
const ui = useUiStore()
const { date } = useFormat()

watch(
  () => store.current?.id,
  () => {
    if (store.current && store.documents === null) store.fetchDocuments()
  },
  { immediate: true },
)

const docsByType = computed(() => {
  const map = { quotation: [], tds: [], result: [] }
  for (const d of store.documents || []) (map[d.docType] ??= []).push(d)
  return map
})

// --- Upload modal ---
const uploadType = ref(null) // doc type slug while the modal is open
const selected = ref([])
const uploading = ref(false)
const fileInput = ref(null)

function openUpload(type) {
  uploadType.value = type
  selected.value = []
}
function pickFiles() {
  fileInput.value?.click()
}
function onPick(e) {
  const rejected = []
  for (const f of e.target.files || []) {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      rejected.push(f.name)
      continue
    }
    if (!selected.value.some((s) => s.name === f.name && s.size === f.size)) {
      selected.value.push(f)
    }
  }
  if (rejected.length) ui.error(`Only PDF files are allowed: ${rejected.join(', ')}`)
  e.target.value = '' // allow re-picking the same file
}
function removeSelected(i) {
  selected.value.splice(i, 1)
}

async function submitUpload() {
  if (!selected.value.length || uploading.value) return
  uploading.value = true
  try {
    const items = await store.uploadDocuments(uploadType.value, selected.value)
    ui.success(`Uploaded ${items.length} ${LABELS[uploadType.value]} document(s)`)
    uploadType.value = null
  } catch (e) {
    ui.error(e.message)
  } finally {
    uploading.value = false
  }
}

// --- Row actions ---
async function download(doc) {
  try {
    const blob = await api.downloadDocument(doc.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.name
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ui.error(e.message)
  }
}

async function remove(doc) {
  if (!confirm(`Delete "${doc.name}"?`)) return
  try {
    await store.removeDocument(doc.id)
  } catch (e) {
    ui.error(e.message)
  }
}

function fmtSize(bytes) {
  if (bytes == null) return '—'
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}
</script>

<template>
  <section class="docs panel">
    <div v-for="[type, label] in DOC_TYPES" :key="type" class="doc-sec">
      <header class="ds-head">
        <h3 class="sec-title">{{ label }} <span>{{ docsByType[type].length }}</span></h3>
        <button class="btn sm" @click="openUpload(type)">
          <AppIcon name="plus" :size="14" />
          {{ label }}
        </button>
      </header>

      <div v-if="store.documentsLoading && store.documents === null" class="empty">
        Loading...
      </div>

      <div v-else-if="docsByType[type].length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Size</th>
              <th>Uploaded by</th>
              <th>Date</th>
              <th class="actions-col" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in docsByType[type]" :key="doc.id">
              <td class="name" :title="doc.name">
                <AppIcon name="doc" :size="13" />
                {{ doc.name }}
              </td>
              <td class="num">{{ fmtSize(doc.size) }}</td>
              <td>{{ doc.user?.name || '—' }}</td>
              <td>{{ date(doc.createdAt) }}</td>
              <td class="actions-col">
                <button class="del" title="Download" @click="download(doc)">
                  <AppIcon name="download" :size="13" />
                </button>
                <button class="del" title="Delete" @click="remove(doc)">
                  <AppIcon name="trash" :size="13" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-else class="empty">No {{ label.toLowerCase() }} documents yet.</p>
    </div>

    <Modal
      v-if="uploadType"
      :title="`Upload ${LABELS[uploadType]}`"
      @close="uploadType = null"
    >
      <div class="up-body">
        <button class="btn ghost" @click="pickFiles">
          <AppIcon name="plus" :size="14" />
          Choose PDF files
        </button>
        <input
          ref="fileInput"
          type="file"
          accept="application/pdf,.pdf"
          multiple
          class="hidden-file"
          @change="onPick"
        />
        <p class="hint">PDF only · multiple files allowed</p>

        <ul v-if="selected.length" class="picked">
          <li v-for="(f, i) in selected" :key="f.name + f.size">
            <AppIcon name="doc" :size="13" />
            <span class="pk-name" :title="f.name">{{ f.name }}</span>
            <span class="pk-size">{{ fmtSize(f.size) }}</span>
            <button class="del" title="Remove" @click="removeSelected(i)">
              <AppIcon name="close" :size="12" />
            </button>
          </li>
        </ul>
        <p v-else class="empty">No files selected.</p>
      </div>

      <template #footer>
        <button class="btn ghost" :disabled="uploading" @click="uploadType = null">
          Cancel
        </button>
        <button class="btn" :disabled="uploading || !selected.length" @click="submitUpload">
          {{ uploading ? 'Uploading...' : `Upload ${selected.length} file(s)` }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.docs { display: grid; gap: 18px; }
.doc-sec { display: grid; gap: 10px; }
.ds-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
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
td.name {
  display: flex; align-items: center; gap: 6px;
  max-width: 260px; overflow: hidden; text-overflow: ellipsis;
}
td.num { font-variant-numeric: tabular-nums; }
.actions-col { width: 1%; text-align: right; }
td.actions-col { display: flex; gap: 4px; justify-content: flex-end; }
.del { display: grid; place-items: center; background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 3px; opacity: .6; }
.del:hover { opacity: 1; color: var(--accent); }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; padding: 8px 0; }

/* Upload modal */
.up-body { display: grid; gap: 10px; justify-items: start; }
.hidden-file { display: none; }
.hint { font-size: 11px; color: var(--text-dim); margin: 0; }
.picked { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; width: 100%; }
.picked li {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px;
  font-size: 12px; color: var(--text); background: var(--bg-sunken);
}
.pk-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pk-size { color: var(--text-dim); font-variant-numeric: tabular-nums; }
</style>

<script setup>
// Popup shown when exporting a saved BOM list to PDF. Lets the user append the
// target project's uploaded PDF documents (quotation / technical datasheet /
// result) onto the generated BOM PDF. Checked types contribute every document
// of that type; checking nothing produces the plain BOM PDF.
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import { useUiStore } from '@/stores/ui'
import { exportBomListPdf } from '@/utils/recordExport'
import Modal from './Modal.vue'

const props = defineProps({
  project: { type: Object, required: true },
  listName: { type: String, default: '' },
  rows: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])

const ui = useUiStore()

// Ordered so checked docs append quotation -> tds -> result.
const TYPES = [
  ['quotation', 'Quotation'],
  ['tds', 'Technical Datasheet'],
  ['result', 'Result'],
]

const loading = ref(true)
const exporting = ref(false)
const docsByType = ref({ quotation: [], tds: [], result: [] })
const checked = ref({ quotation: false, tds: false, result: false })

const hasAnyDoc = () => TYPES.some(([t]) => docsByType.value[t].length)

onMounted(async () => {
  if (!props.project?.id) {
    loading.value = false
    return
  }
  try {
    const res = await api.listDocuments(props.project.id)
    const map = { quotation: [], tds: [], result: [] }
    for (const d of res.items || []) (map[d.docType] ??= []).push(d)
    docsByType.value = map
  } catch (e) {
    ui.error(e.message)
  } finally {
    loading.value = false
  }
})

async function doExport() {
  exporting.value = true
  try {
    // Collect checked types' documents in quotation -> tds -> result order.
    const attachments = []
    for (const [type] of TYPES) {
      if (!checked.value[type]) continue
      for (const doc of docsByType.value[type]) {
        const blob = await api.downloadDocument(doc.id)
        attachments.push({ name: doc.name, bytes: await blob.arrayBuffer() })
      }
    }
    const { failed } = await exportBomListPdf(
      props.project,
      props.listName,
      props.rows,
      { attachments },
    )
    if (failed && failed.length)
      ui.error(`Skipped ${failed.length} unreadable file(s): ${failed.join(', ')}`)
    else ui.success(`Exported "${props.listName}" to PDF`)
    emit('close')
  } catch (e) {
    ui.error(e.message)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <Modal :title="`Export &quot;${listName}&quot; — attach documents`" @close="emit('close')">
    <p v-if="loading" class="ed-hint">Loading documents…</p>
    <template v-else>
      <p v-if="!hasAnyDoc()" class="ed-hint">
        This project has no uploaded documents. Export produces the BOM list only.
      </p>
      <div v-else class="ed-list">
        <label
          v-for="[type, label] in TYPES"
          :key="type"
          class="ed-row"
          :class="{ disabled: !docsByType[type].length }"
        >
          <input
            type="checkbox"
            v-model="checked[type]"
            :disabled="!docsByType[type].length"
          />
          <span class="ed-label">{{ label }}</span>
          <span class="ed-count">{{ docsByType[type].length }}</span>
        </label>
      </div>
    </template>

    <template #footer>
      <button class="btn ghost" @click="emit('close')" :disabled="exporting">
        Cancel
      </button>
      <button class="btn" @click="doExport" :disabled="loading || exporting">
        {{ exporting ? 'Exporting…' : 'Export PDF' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.ed-hint {
  color: var(--muted);
  font-size: 13px;
  margin: 0;
}
.ed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ed-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
}
.ed-row.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ed-label {
  flex: 1;
  font-size: 14px;
  color: var(--text);
}
.ed-count {
  font-size: 12px;
  color: var(--muted);
  background: var(--lc-base-strong);
  border-radius: 999px;
  padding: 2px 9px;
  font-variant-numeric: tabular-nums;
}
</style>

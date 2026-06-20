<script setup>
// Renders the import preview produced by recordExport.js. Accepts both the
// single-resource shape ({valid, errors, unmatched}) and the multi-resource
// shape ({perResource: {[r]: single-shape}, unknownSheets}). The parent owns
// the actual write loop and toggles `importing` while it runs.
import { computed } from 'vue'
import { RECORD_SCHEMAS } from '@/schemas/records'
import Modal from './Modal.vue'

const props = defineProps({
  title: { type: String, required: true },
  // Single-resource: { valid, errors, unmatched }
  // Multi-resource:  { perResource: { [r]: {valid, errors, unmatched} }, unknownSheets }
  result: { type: Object, required: true },
  importing: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'confirm'])

const isMulti = computed(
  () => props.result && typeof props.result === 'object' && 'perResource' in props.result,
)

const perResourceEntries = computed(() => {
  if (!isMulti.value) return []
  return Object.entries(props.result.perResource).map(([resource, r]) => ({
    resource,
    label: RECORD_SCHEMAS[resource]?.label || resource,
    valid: r.valid || [],
    errors: r.errors || [],
    unmatched: r.unmatched || [],
  }))
})

const totalValid = computed(() => {
  if (isMulti.value) {
    return perResourceEntries.value.reduce((a, x) => a + x.valid.length, 0)
  }
  return props.result?.valid?.length || 0
})

const totalErrors = computed(() => {
  if (isMulti.value) {
    return perResourceEntries.value.reduce((a, x) => a + x.errors.length, 0)
  }
  return props.result?.errors?.length || 0
})

const unknownSheets = computed(() => (isMulti.value ? props.result.unknownSheets || [] : []))
const singleUnmatched = computed(() => (isMulti.value ? [] : props.result?.unmatched || []))

const confirmLabel = computed(() =>
  props.importing ? 'Importing…' : `Import ${totalValid.value} record(s)`,
)
</script>

<template>
  <Modal wide :title="title" @close="emit('close')">
    <div class="summary">
      <p>
        <strong>{{ totalValid }}</strong> valid row(s)<span v-if="totalErrors">,
          <strong class="bad">{{ totalErrors }}</strong> with errors</span>.
      </p>
      <p v-if="singleUnmatched.length" class="warn">
        Ignored unmatched column(s): {{ singleUnmatched.join(', ') }}
      </p>
      <p v-if="unknownSheets.length" class="warn">
        Ignored unknown sheet(s): {{ unknownSheets.join(', ') }}
      </p>
    </div>

    <!-- Multi-resource: one block per resource -->
    <template v-if="isMulti">
      <div v-for="r in perResourceEntries" :key="r.resource" class="r-block">
        <div class="r-head">
          <strong>{{ r.label }}</strong>
          <span class="meta">
            {{ r.valid.length }} valid<span v-if="r.errors.length">,
              {{ r.errors.length }} error(s)</span>
          </span>
        </div>
        <p v-if="r.unmatched.length" class="warn small">
          Ignored unmatched column(s): {{ r.unmatched.join(', ') }}
        </p>
        <div v-if="r.errors.length" class="table-wrap err-table">
          <table>
            <thead>
              <tr><th>Row</th><th>Column</th><th>Problem</th></tr>
            </thead>
            <tbody>
              <tr v-for="(e, i) in r.errors" :key="i">
                <td class="num">{{ e.row }}</td>
                <td>{{ e.column }}</td>
                <td>{{ e.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- Single-resource: one error table -->
    <div v-else-if="(result.errors || []).length" class="table-wrap err-table">
      <table>
        <thead>
          <tr><th>Row</th><th>Column</th><th>Problem</th></tr>
        </thead>
        <tbody>
          <tr v-for="(e, i) in result.errors" :key="i">
            <td class="num">{{ e.row }}</td>
            <td>{{ e.column }}</td>
            <td>{{ e.message }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <template #footer>
      <button class="btn ghost" @click="emit('close')">Cancel</button>
      <button class="btn" :disabled="!totalValid || importing" @click="emit('confirm')">
        {{ confirmLabel }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.summary { font-size: 13px; color: var(--text); margin-bottom: 12px; }
.summary .bad { color: var(--danger, #dc2626); }
.summary .warn { color: var(--text-dim); font-size: 12px; margin-top: 4px; }

.r-block {
  margin-top: 16px; padding: 10px 12px;
  border: 1px solid var(--border); border-radius: 8px;
  background: var(--bg-sunken);
}
.r-head {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 13px; color: var(--text); margin-bottom: 6px;
}
.r-head .meta { font-size: 12px; color: var(--text-dim); }
.warn.small { font-size: 11px; }

.table-wrap { max-height: 240px; overflow: auto; border: 1px solid var(--border); border-radius: 6px; margin-top: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
th {
  background: var(--surface); font-weight: 700; color: var(--text-dim);
  font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
}
td.num { text-align: center; font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: 0; }
.err-table { max-height: 320px; }
</style>

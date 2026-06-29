<script setup>
// Add/edit form for the global BOM page. Unlike the schema-driven RecordForm
// (which posts under a fixed `/api/projects/<pid>/...` URL), this form also
// carries a Project picker so the user chooses which project the new record
// belongs to. On edit the picker is locked — moving a record between projects
// isn't supported by the current PATCH /api/records/bom/<id> endpoint.
import { reactive, computed, watch } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { RECORD_SCHEMAS, emptyRecord } from '@/schemas/records'

const props = defineProps({
  record: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const projectsStore = useProjectsStore()
const schema = RECORD_SCHEMAS.bom
const isEdit = computed(() => !!props.record)

const projectOptions = computed(() =>
  [...projectsStore.projects].sort((a, b) =>
    (a.name || '').localeCompare(b.name || ''),
  ),
)

const base = emptyRecord('bom')
const form = reactive({ projectId: props.record?.projectId ?? null, ...base })
if (props.record) {
  for (const f of schema.fields) {
    const v = props.record[f.key]
    if (v != null) form[f.key] = f.type === 'date' ? String(v).slice(0, 10) : v
  }
}

// totalPrice is derived: quantity × unitPrice. The field is read-only; this
// watcher (immediate) also corrects any stale persisted total on edit, so the
// formula is always the source of truth.
watch(
  () => [form.quantity, form.unitPrice],
  ([q, u]) => {
    const qn = q === '' || q == null ? null : Number(q)
    const un = u === '' || u == null ? null : Number(u)
    form.totalPrice = qn != null && un != null && !isNaN(qn) && !isNaN(un) ? qn * un : null
  },
  { immediate: true },
)

const invalid = computed(() => !form.projectId)

function submit() {
  if (invalid.value) return
  const out = { projectId: form.projectId }
  for (const f of schema.fields) {
    let v = form[f.key]
    if (f.type === 'number') v = v === '' || v == null ? null : Number(v)
    else if (f.type === 'date') v = v || null
    out[f.key] = v
  }
  emit('submit', out)
}
</script>

<template>
  <form class="rform" @submit.prevent="submit">
    <div class="grid">
      <label class="field span2">
        <span>Project<em v-if="!isEdit" class="req">*</em></span>
        <select v-model="form.projectId" class="input" :disabled="isEdit">
          <option :value="null" disabled>Select a project…</option>
          <option v-for="p in projectOptions" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </label>

      <label
        v-for="f in schema.fields"
        :key="f.key"
        class="field"
        :class="{ span2: f.type === 'textarea', check: f.type === 'checkbox' }"
      >
        <span>{{ f.label }}</span>
        <textarea
          v-if="f.type === 'textarea'"
          v-model="form[f.key]"
          class="input"
          rows="2"
        />
        <input
          v-else-if="f.type === 'date'"
          v-model="form[f.key]"
          type="date"
          class="input"
        />
        <input
          v-else-if="f.key === 'totalPrice'"
          :value="form.totalPrice ?? ''"
          type="number"
          class="input computed"
          readonly
          tabindex="-1"
          title="Auto-calculated: Unit price × Quantity"
        />
        <input
          v-else-if="f.type === 'number'"
          v-model="form[f.key]"
          type="number"
          class="input"
        />
        <input
          v-else-if="f.type === 'checkbox'"
          v-model="form[f.key]"
          type="checkbox"
          class="checkbox"
        />
        <input v-else v-model="form[f.key]" class="input" />
      </label>
    </div>

    <div class="actions">
      <button type="button" class="btn ghost" @click="emit('cancel')">Cancel</button>
      <button type="submit" class="btn" :disabled="submitting || invalid">
        {{ submitting ? 'Saving...' : (isEdit ? 'Save changes' : 'Add record') }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.rform { display: grid; gap: 16px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.span2 { grid-column: 1 / -1; }
.field { display: grid; gap: 5px; }
.field > span {
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .05em;
  text-transform: uppercase;
}
.req { color: var(--accent); font-style: normal; margin-left: 2px; }
.field.check {
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 8px;
}
.field.check > span { order: 2; text-transform: none; font-size: 12px; }
.checkbox { width: 16px; height: 16px; accent-color: var(--accent); }
select.input { appearance: auto; }
select.input:disabled { opacity: .7; cursor: not-allowed; }
.input.computed {
  background: var(--bg-sunken);
  color: var(--text-dim);
  cursor: not-allowed;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
  .span2 { grid-column: auto; }
}
</style>

<script setup>
import { reactive } from 'vue'
import { RECORD_SCHEMAS, emptyRecord } from '@/schemas/records'

const props = defineProps({
  resource: { type: String, required: true },
  record: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const schema = RECORD_SCHEMAS[props.resource]

// Seed the form from the existing record (edit) or blank defaults (create).
const base = emptyRecord(props.resource)
const form = reactive({ ...base })
if (props.record) {
  for (const f of schema.fields) {
    const v = props.record[f.key]
    if (v != null) form[f.key] = f.type === 'date' ? String(v).slice(0, 10) : v
  }
}

function submit() {
  const out = {}
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
      <button type="submit" class="btn" :disabled="submitting">
        {{ submitting ? 'Saving...' : (record ? 'Save changes' : 'Add record') }}
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
.field.check {
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 8px;
}
.field.check > span { order: 2; text-transform: none; font-size: 12px; }
.checkbox { width: 16px; height: 16px; accent-color: var(--accent); }
.actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
  .span2 { grid-column: auto; }
}
</style>

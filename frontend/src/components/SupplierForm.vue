<script setup>
// Add/edit form for the supplier directory. `supplier` null = create mode,
// object = edit mode (mirrors BomGlobalForm's `record` prop pattern). Only
// `name` is required; every other field is optional free text. Write access
// is admin-only — enforced by the backend (suppliers.create/suppliers.update)
// and gated in the parent view via auth.hasPermission().
import { reactive, computed } from 'vue'

const props = defineProps({
  supplier: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const isEdit = computed(() => !!props.supplier)

const form = reactive({
  name: props.supplier?.name || '',
  code: props.supplier?.code || '',
  description: props.supplier?.description || '',
  address: props.supplier?.address || '',
  telephone: props.supplier?.telephone || '',
  mobile: props.supplier?.mobile || '',
  email: props.supplier?.email || '',
  lineAcc: props.supplier?.lineAcc || '',
  website: props.supplier?.website || '',
  taxId: props.supplier?.taxId || '',
})

const invalid = computed(() => !String(form.name || '').trim())

function submit() {
  if (invalid.value) return
  const out = {}
  for (const k of Object.keys(form)) {
    const v = String(form[k] ?? '').trim()
    out[k] = v || null
  }
  emit('submit', out)
}
</script>

<template>
  <form class="rform" @submit.prevent="submit">
    <div class="grid">
      <label class="field">
        <span>Supplier name<em class="req">*</em></span>
        <input v-model="form.name" class="input" />
      </label>
      <label class="field">
        <span>Code</span>
        <input v-model="form.code" class="input" />
      </label>
      <label class="field span2">
        <span>Description</span>
        <textarea v-model="form.description" class="input" rows="2" />
      </label>
      <label class="field span2">
        <span>Address</span>
        <textarea v-model="form.address" class="input" rows="2" />
      </label>
      <label class="field">
        <span>Telephone</span>
        <input v-model="form.telephone" class="input" />
      </label>
      <label class="field">
        <span>Mobile</span>
        <input v-model="form.mobile" class="input" />
      </label>
      <label class="field">
        <span>Email</span>
        <input v-model="form.email" class="input" type="email" />
      </label>
      <label class="field">
        <span>LINE</span>
        <input v-model="form.lineAcc" class="input" />
      </label>
      <label class="field">
        <span>Website</span>
        <input v-model="form.website" class="input" />
      </label>
      <label class="field">
        <span>Tax ID</span>
        <input v-model="form.taxId" class="input" />
      </label>
    </div>
    <div class="actions">
      <button type="button" class="btn ghost" @click="emit('cancel')">Cancel</button>
      <button type="submit" class="btn" :disabled="submitting || invalid">
        {{ submitting ? 'Saving...' : (isEdit ? 'Save changes' : 'Add supplier') }}
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
.actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
  .span2 { grid-column: auto; }
}
</style>

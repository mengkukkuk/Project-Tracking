<script setup>
// Profile card for the supplier picked in the BOM filter bar. `supplier` is
// the matched pjtrk.supplier row (camelCase dict) or null when the free-text
// filter value has no profile on record. Edit/Add are admin-gated
// (suppliers.update/suppliers.create) — the parent view resolves the
// permission via auth.hasPermission() and passes it down as a plain boolean,
// keeping this component free of store/auth access.
import AppIcon from './AppIcon.vue'

defineProps({
  supplier: { type: Object, default: null },
  label: { type: String, default: '' },
  canEdit: { type: Boolean, default: false },
  canCreate: { type: Boolean, default: false },
})
defineEmits(['edit', 'add'])
</script>

<template>
  <aside class="supplier-card" aria-label="Supplier information">
    <template v-if="supplier">
      <div class="sc-head">
        <strong class="sc-name">{{ supplier.name || supplier.code }}</strong>
        <span v-if="supplier.code" class="sc-code">{{ supplier.code }}</span>
        <button
          v-if="canEdit"
          type="button"
          class="icon-btn sc-edit"
          aria-label="Edit supplier"
          @click="$emit('edit')"
        >
          <AppIcon name="edit" :size="14" />
        </button>
        <span v-if="supplier.taxId" class="sc-tax mono">Tax ID {{ supplier.taxId }}</span>
      </div>
      <p v-if="supplier.description" class="sc-desc">{{ supplier.description }}</p>
      <div class="sc-grid">
        <div v-if="supplier.address" class="sc-item sc-wide">
          <span class="sc-label">Address</span>
          <span class="sc-pre">{{ supplier.address }}</span>
        </div>
        <div v-if="supplier.telephone" class="sc-item">
          <span class="sc-label">Telephone</span>
          <span>{{ supplier.telephone }}</span>
        </div>
        <div v-if="supplier.mobile" class="sc-item">
          <span class="sc-label">Mobile</span>
          <span>{{ supplier.mobile }}</span>
        </div>
        <div v-if="supplier.email" class="sc-item">
          <span class="sc-label">Email</span>
          <a :href="`mailto:${supplier.email}`">{{ supplier.email }}</a>
        </div>
        <div v-if="supplier.lineAcc" class="sc-item">
          <span class="sc-label">LINE</span>
          <span>{{ supplier.lineAcc }}</span>
        </div>
        <div v-if="supplier.website" class="sc-item">
          <span class="sc-label">Website</span>
          <a :href="supplier.website" target="_blank" rel="noopener">{{ supplier.website }}</a>
        </div>
      </div>
    </template>
    <template v-else>
      <p class="sc-empty">No supplier profile on record for "{{ label }}".</p>
      <button v-if="canCreate" type="button" class="btn ghost sc-add" @click="$emit('add')">
        <AppIcon name="plus" :size="14" /> Add supplier
      </button>
    </template>
  </aside>
</template>

<style scoped>
.supplier-card {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
  border-radius: 8px;
  background: color-mix(in srgb, var(--accent) 5%, var(--surface));
  font-size: 13px;
  color: var(--text);
}
.sc-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sc-name { font-weight: 600; font-size: 14px; }
.sc-code {
  padding: 2px 8px;
  border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
  border-radius: 999px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
}
.sc-edit { width: 22px; height: 22px; }
.sc-tax { margin-left: auto; color: var(--text-dim); font-size: 11px; font-weight: 600; }
.sc-desc { margin: 0; color: var(--text-dim); white-space: pre-line; }
.sc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px 18px;
}
.sc-item { display: grid; gap: 2px; min-width: 0; }
.sc-wide { grid-column: 1 / -1; }
.sc-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--text-dim);
}
.sc-pre { white-space: pre-line; }
.sc-item a { color: var(--accent); text-decoration: none; overflow-wrap: anywhere; }
.sc-item a:hover { text-decoration: underline; }
.sc-empty { margin: 0; color: var(--text-dim); font-style: italic; }
.sc-add { margin-top: 6px; }
</style>

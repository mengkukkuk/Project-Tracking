<script setup>
import { reactive, ref, computed } from 'vue'
import { STAGES } from '@/stores/projects'

const props = defineProps({
  project: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const DOMAINS = ['Vision Sensor', 'Robot', 'PLC', 'IoT', 'AI']
const PRIORITIES = [
  ['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['critical', 'Critical'],
]
const FYS = ['69', '70', '71', 'future']

const p = props.project
const form = reactive({
  name: p?.name || '',
  description: p?.description || '',
  domain: p?.domain || 'IoT',
  customer: p?.customer || '',
  pm: p?.pm || '',
  status: p?.status || 'Pre-Sale',
  priority: p?.priority || 'medium',
  value: p?.value ?? 0,
  progress: p?.progress ?? 0,
  fiscalYear: p?.fiscalYear || 'future',
  startDate: p?.startDate || '',
  dueDate: p?.dueDate || '',
})
const tagsInput = ref((p?.tags || []).map((t) => t.name).join(', '))
const tags = computed(() => tagsInput.value.split(',').map((s) => s.trim()).filter(Boolean))

function submit() {
  emit('submit', {
    ...form,
    value: Number(form.value) || 0,
    progress: Number(form.progress) || 0,
    startDate: form.startDate || null,
    dueDate: form.dueDate || null,
    tags: tags.value,
  })
}
</script>

<template>
  <form class="pform" @submit.prevent="submit">
    <section class="group span2">
      <h3>Identity</h3>
      <div class="grid">
        <label class="field span2">
          <span>Project name *</span>
          <input v-model="form.name" class="input" required maxlength="255" />
        </label>

        <label class="field span2">
          <span>Description</span>
          <textarea v-model="form.description" class="input" rows="2" />
        </label>

        <label class="field">
          <span>Domain</span>
          <select v-model="form.domain" class="select">
            <option v-for="d in DOMAINS" :key="d" :value="d">{{ d }}</option>
          </select>
        </label>

        <label class="field">
          <span>Customer</span>
          <input v-model="form.customer" class="input" maxlength="255" />
        </label>

        <label class="field">
          <span>Project manager</span>
          <input v-model="form.pm" class="input" maxlength="128" />
        </label>

        <label class="field">
          <span>Tags</span>
          <input v-model="tagsInput" class="input" placeholder="urgent, retrofit, internal" />
        </label>

        <div v-if="tags.length" class="chips span2">
          <span v-for="tag in tags" :key="tag">{{ tag }}</span>
        </div>
      </div>
    </section>

    <section class="group span2">
      <h3>Planning</h3>
      <div class="grid">
        <label class="field">
          <span>Status</span>
          <select v-model="form.status" class="select">
            <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>

        <label class="field">
          <span>Priority</span>
          <select v-model="form.priority" class="select">
            <option v-for="[v, l] in PRIORITIES" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>

        <label class="field">
          <span>Fiscal year</span>
          <select v-model="form.fiscalYear" class="select">
            <option v-for="y in FYS" :key="y" :value="y">{{ y === 'future' ? 'Future' : `FY${y}` }}</option>
          </select>
        </label>

        <label class="field">
          <span>Value (THB)</span>
          <input v-model="form.value" type="number" min="0" step="100000" class="input" />
        </label>

        <label class="field">
          <span>Start date</span>
          <input v-model="form.startDate" type="date" class="input" />
        </label>

        <label class="field">
          <span>Due date</span>
          <input v-model="form.dueDate" type="date" class="input" />
        </label>

        <label class="field span2 progress-field">
          <span>Progress: {{ form.progress }}%</span>
          <input v-model="form.progress" type="range" min="0" max="100" step="5" />
        </label>
      </div>
    </section>

    <div class="actions span2">
      <button type="button" class="btn ghost" @click="emit('cancel')">Cancel</button>
      <button type="submit" class="btn" :disabled="submitting">
        {{ submitting ? 'Saving...' : (project ? 'Save changes' : 'Create project') }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.pform { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.span2 { grid-column: 1 / -1; }
.group {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  background: var(--bg-sunken);
}
.group h3 {
  margin: 0 0 12px;
  color: var(--text);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chips span {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
  border-radius: 6px;
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 700;
}
.progress-field input {
  width: 100%;
  accent-color: var(--accent);
}
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
@media (max-width: 640px) {
  .pform,
  .grid { grid-template-columns: 1fr; }
  .span2 { grid-column: auto; }
}
</style>

<script setup>
import { reactive, ref } from 'vue'
import { STAGES } from '@/stores/projects'

const props = defineProps({
  project: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const DOMAINS = ['Vision Sensor', 'Robot', 'PLC', 'IoT', 'AI']
const PRIORITIES = [
  ['low', 'ต่ำ'], ['medium', 'ปานกลาง'], ['high', 'สูง'], ['critical', 'วิกฤต'],
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

function submit() {
  const tags = tagsInput.value.split(',').map((s) => s.trim()).filter(Boolean)
  emit('submit', {
    ...form,
    value: Number(form.value) || 0,
    progress: Number(form.progress) || 0,
    startDate: form.startDate || null,
    dueDate: form.dueDate || null,
    tags,
  })
}
</script>

<template>
  <form class="pform" @submit.prevent="submit">
    <label class="field span2">
      <span>ชื่อโครงการ *</span>
      <input v-model="form.name" class="input" required maxlength="255" />
    </label>

    <label class="field span2">
      <span>รายละเอียด</span>
      <textarea v-model="form.description" class="input" rows="2" />
    </label>

    <label class="field">
      <span>กลุ่มงาน</span>
      <select v-model="form.domain" class="select">
        <option v-for="d in DOMAINS" :key="d" :value="d">{{ d }}</option>
      </select>
    </label>

    <label class="field">
      <span>ลูกค้า</span>
      <input v-model="form.customer" class="input" maxlength="255" />
    </label>

    <label class="field">
      <span>ผู้จัดการโครงการ (PM)</span>
      <input v-model="form.pm" class="input" maxlength="128" />
    </label>

    <label class="field">
      <span>สถานะ</span>
      <select v-model="form.status" class="select">
        <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
      </select>
    </label>

    <label class="field">
      <span>ความสำคัญ</span>
      <select v-model="form.priority" class="select">
        <option v-for="[v, l] in PRIORITIES" :key="v" :value="v">{{ l }}</option>
      </select>
    </label>

    <label class="field">
      <span>ปีงบประมาณ</span>
      <select v-model="form.fiscalYear" class="select">
        <option v-for="y in FYS" :key="y" :value="y">{{ y === 'future' ? 'ในอนาคต' : y }}</option>
      </select>
    </label>

    <label class="field">
      <span>มูลค่า (บาท)</span>
      <input v-model="form.value" type="number" min="0" step="100000" class="input" />
    </label>

    <label class="field">
      <span>ความคืบหน้า (%)</span>
      <input v-model="form.progress" type="number" min="0" max="100" class="input" />
    </label>

    <label class="field">
      <span>วันเริ่ม</span>
      <input v-model="form.startDate" type="date" class="input" />
    </label>

    <label class="field">
      <span>กำหนดส่ง</span>
      <input v-model="form.dueDate" type="date" class="input" />
    </label>

    <label class="field span2">
      <span>ป้ายกำกับ (คั่นด้วย ,)</span>
      <input v-model="tagsInput" class="input" placeholder="เช่น กรมสรรพสามิต, เร่งด่วน" />
    </label>

    <div class="actions span2">
      <button type="button" class="btn ghost" @click="emit('cancel')">ยกเลิก</button>
      <button type="submit" class="btn" :disabled="submitting">
        {{ submitting ? 'กำลังบันทึก...' : (project ? 'บันทึก' : 'สร้างโครงการ') }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.pform { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.span2 { grid-column: 1 / -1; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
@media (max-width: 560px) { .pform { grid-template-columns: 1fr; } }
</style>

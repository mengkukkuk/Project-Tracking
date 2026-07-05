<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, required: true },
  label: { type: String, required: true },
  color: { type: String, required: true },
  size: { type: Number, default: 64 },
})

const r = 28
const circ = 2 * Math.PI * r
const dash = computed(() => (clamp(props.value) / 100) * circ)

function clamp(v) {
  return Math.min(100, Math.max(0, v || 0))
}
</script>

<template>
  <div class="ring-gauge">
    <div class="ring-wrap" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 72 72" class="ring-svg">
        <circle cx="36" cy="36" :r="r" fill="none" stroke="var(--border)" stroke-width="6" />
        <circle
          cx="36" cy="36" :r="r"
          fill="none"
          :stroke="color"
          stroke-width="6"
          stroke-linecap="round"
          :stroke-dasharray="`${dash} ${circ}`"
          class="ring-progress"
        />
      </svg>
      <span class="ring-value mono readout">{{ Math.round(value) }}</span>
    </div>
    <span class="ring-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.ring-gauge { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.ring-wrap { position: relative; }
.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring-progress { transition: stroke-dasharray .3s ease; }
.ring-value {
  position: absolute; inset: 0;
  display: grid; place-items: center;
  font-size: 12px; font-weight: 700; color: var(--text);
}
.ring-label { font-size: 11px; color: var(--text-dim); text-align: center; line-height: 1.2; }
</style>

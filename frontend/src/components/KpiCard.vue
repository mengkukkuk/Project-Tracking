<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  label: String,
  value: [String, Number],
  sub: String,
  icon: String,
  accent: { type: String, default: '#14b8a6' },
  actionable: Boolean,
})

defineEmits(['click'])
</script>

<template>
  <button
    v-if="actionable"
    type="button"
    class="kpi card actionable"
    @click="$emit('click')"
  >
    <span class="kpi-icon" :style="{ background: accent + '1a', color: accent }">
      <AppIcon v-if="icon" :name="icon" :size="20" />
    </span>
    <span class="kpi-body">
      <span class="kpi-label">{{ label }}</span>
      <span class="kpi-value mono">{{ value }}</span>
      <span v-if="sub" class="kpi-sub">{{ sub }}</span>
    </span>
  </button>
  <div v-else class="kpi card">
    <div class="kpi-icon" :style="{ background: accent + '1a', color: accent }">
      <AppIcon v-if="icon" :name="icon" :size="20" />
    </div>
    <div class="kpi-body">
      <div class="kpi-label">{{ label }}</div>
      <div class="kpi-value mono">{{ value }}</div>
      <div v-if="sub" class="kpi-sub">{{ sub }}</div>
    </div>
  </div>
</template>

<style scoped>
.kpi {
  width: 100%;
  display: flex; align-items: center; gap: 14px; padding: 16px 18px;
  text-align: left; border-color: var(--border);
  transition: transform .15s, box-shadow .15s, border-color .15s;
}
button.kpi {
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.kpi:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.kpi.actionable:hover { border-color: var(--accent); }
.kpi-icon {
  width: 42px; height: 42px; border-radius: 8px; flex-shrink: 0;
  display: grid; place-items: center;
}
.kpi-body {
  display: grid;
  min-width: 0;
}
.kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-dim); font-weight: 700; }
.kpi-value { font-size: 24px; font-weight: 700; color: var(--text); margin-top: 3px; line-height: 1.1; }
.kpi-sub { font-size: 11px; color: var(--text-dim); margin-top: 3px; }
</style>

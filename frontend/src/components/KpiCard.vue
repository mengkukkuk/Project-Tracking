<script setup>
defineProps({
  label: String,
  value: [String, Number],
  sub: String,
  icon: String,
  accent: { type: String, default: '#14b8a6' },
})
</script>

<template>
  <div class="kpi card">
    <div class="kpi-icon" :style="{ background: accent + '1a', color: accent }">
      {{ icon }}
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
  display: flex; align-items: center; gap: 14px; padding: 16px 18px;
  transition: transform .15s, box-shadow .15s;
}
.kpi:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.kpi-icon {
  width: 42px; height: 42px; border-radius: 11px; flex-shrink: 0;
  display: grid; place-items: center; font-size: 19px;
}
.kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-dim); font-weight: 600; }
.kpi-value { font-size: 24px; font-weight: 600; color: var(--text); margin-top: 3px; line-height: 1.1; }
.kpi-sub { font-size: 11px; color: var(--text-dim); margin-top: 3px; }
</style>

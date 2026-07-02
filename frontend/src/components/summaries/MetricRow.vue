<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  formula: { type: String, default: '' },
  highlight: { type: Boolean, default: false },
})
</script>

<template>
  <div class="metric-row" :class="{ highlight }">
    <div class="metric-text">
      <p class="metric-label">{{ label }}</p>
      <p v-if="formula" class="metric-formula mono">{{ formula }}</p>
    </div>
    <span class="metric-value mono">{{ value }}</span>
  </div>
</template>

<style scoped>
.metric-row {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;
  padding: 8px 0; border-bottom: 1px solid var(--border);
}
.metric-row:last-child { border-bottom: 0; }
.metric-row.highlight {
  background: color-mix(in srgb, var(--accent) 6%, transparent);
  margin: 0 -10px; padding: 8px 10px; border-radius: 6px; border-bottom-color: transparent;
}
.metric-text { min-width: 0; }
.metric-label { font-size: 12.5px; color: var(--text); }
.metric-formula { font-size: 10.5px; color: var(--text-dim); margin-top: 2px; }
.metric-value { font-size: 13px; font-weight: 700; color: var(--text); flex-shrink: 0; }
.metric-row.highlight .metric-value { color: var(--accent); }
</style>

<script setup>
import { PRIORITY_COLORS } from '@/composables/useChartTheme'
defineProps({ priority: String })

const LABEL = { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' }
</script>

<template>
  <span class="pri" :style="{ color: PRIORITY_COLORS[priority], borderColor: PRIORITY_COLORS[priority] }">
    {{ LABEL[priority] || priority }}
  </span>
</template>

<style scoped>
.pri {
  display: inline-block; padding: 2px 8px; border-radius: 6px;
  font-size: 11px; font-weight: 700; border: 1px solid;
  background: color-mix(in srgb, currentColor 10%, transparent);
}
</style>

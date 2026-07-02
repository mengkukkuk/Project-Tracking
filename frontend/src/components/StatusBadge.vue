<script setup>
defineProps({ status: String })

const COLORS = {
  'Pre-Sale': ['#f59e0b', '#fef3c7'],
  'Project Initiation': ['#3b82f6', '#dbeafe'],
  award: ['#8b5cf6', '#ede9fe'],
  'Project Delivery': ['#14b8a6', '#ccfbf1'],
  Completed: ['#10b981', '#d1fae5'],
}
</script>

<template>
  <span class="badge" :style="{ color: COLORS[status]?.[0], background: COLORS[status]?.[1] }">
    <span class="dot" :style="{ background: COLORS[status]?.[0] }" />
    {{ status }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 600; white-space: nowrap;
}
.dot { width: 6px; height: 6px; border-radius: 50%; }
</style>

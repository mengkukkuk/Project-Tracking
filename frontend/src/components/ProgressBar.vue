<script setup>
defineProps({
  value: { type: Number, default: 0 },
  height: { type: Number, default: 6 },
  showLabel: Boolean,
})
function color(v) {
  if (v >= 100) return '#10b981'
  if (v >= 60) return '#14b8a6'
  if (v >= 30) return '#3b82f6'
  return '#f59e0b'
}
</script>

<template>
  <div class="pb">
    <div class="track" :style="{ height: height + 'px' }">
      <div class="fill" :style="{ width: Math.min(100, value) + '%', background: color(value) }" />
    </div>
    <span v-if="showLabel" class="lbl mono">{{ value }}%</span>
  </div>
</template>

<style scoped>
.pb { display: flex; align-items: center; gap: 8px; }
.track { flex: 1; background: var(--border); border-radius: 99px; overflow: hidden; }
.fill { height: 100%; border-radius: 99px; transition: width .3s ease; }
.lbl { font-size: 11px; color: var(--text-dim); min-width: 34px; text-align: right; }
</style>

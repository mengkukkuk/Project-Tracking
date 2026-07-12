<script setup>
import { useUiStore } from '@/stores/ui'
const ui = useUiStore()
</script>

<template>
  <div class="toast-wrap">
    <TransitionGroup name="toast">
      <div
        v-for="t in ui.toasts"
        :key="t.id"
        class="toast"
        :class="t.type"
        @click="ui.dismiss(t.id)"
      >
        <span class="ico">{{ t.type === 'error' ? '⚠' : '✓' }}</span>
        <span>{{ t.message }}</span>
        <span
          v-if="t.timeout"
          class="toast-bar"
          :style="{ animationDuration: t.timeout + 'ms' }"
        />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-wrap {
  position: fixed; top: 18px; right: 18px; z-index: 1000;
  display: flex; flex-direction: column; gap: 9px; max-width: 360px;
}
.toast {
  position: relative;
  overflow: hidden;
  display: flex; align-items: center; gap: 10px;
  padding: 12px 15px; border-radius: 10px; cursor: pointer;
  background: var(--surface); border: 1px solid var(--border);
  box-shadow: var(--shadow-lg); font-size: 13px; color: var(--text);
  border-left: 3px solid var(--accent);
}
.toast.error { border-left-color: var(--danger); }
.toast-bar {
  position: absolute;
  left: 0; bottom: 0;
  width: 100%; height: 2px;
  background: var(--accent);
  transform-origin: left;
  animation: toast-drain linear forwards;
}
.toast.error .toast-bar { background: var(--danger); }
@keyframes toast-drain {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}
@media (prefers-reduced-motion: reduce) {
  .toast-bar { animation: none; display: none; }
}
.ico {
  display: grid; place-items: center; width: 20px; height: 20px; flex-shrink: 0;
  border-radius: 50%; background: var(--accent); color: #fff; font-size: 12px;
}
.toast.error .ico { background: var(--danger); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(20px); }
.toast-enter-active, .toast-leave-active { transition: all .25s ease; }
</style>

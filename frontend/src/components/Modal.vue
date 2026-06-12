<script setup>
import { onMounted, onUnmounted } from 'vue'

const props = defineProps({
  title: String,
  wide: Boolean,
})
const emit = defineEmits(['close'])

function onKey(e) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="overlay" @click.self="emit('close')">
      <div class="modal" :class="{ wide }">
        <header class="modal-head">
          <h2>{{ title }}</h2>
          <button class="icon-btn" @click="emit('close')" aria-label="ปิด">✕</button>
        </header>
        <div class="modal-body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="modal-foot">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 900;
  background: rgba(15, 23, 42, .5); backdrop-filter: blur(2px);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 6vh 16px; overflow-y: auto;
  animation: ovl .18s ease;
}
@keyframes ovl { from { opacity: 0; } to { opacity: 1; } }
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; box-shadow: var(--shadow-lg);
  width: 100%; max-width: 540px; animation: pop .2s ease;
}
.modal.wide { max-width: 880px; }
@keyframes pop { from { opacity: 0; transform: translateY(-10px) scale(.98); } to { opacity: 1; transform: none; } }
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--border);
}
.modal-head h2 { font-size: 16px; font-weight: 700; color: var(--text); }
.modal-body { padding: 20px; }
.modal-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 14px 20px; border-top: 1px solid var(--border);
}
</style>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import AppIcon from './AppIcon.vue'

defineProps({
  title: String,
  wide: Boolean,
  // Extra-wide variant for table-heavy modals (e.g. the BOM list picker):
  // grows toward a large cap but never past the viewport.
  xwide: Boolean,
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
      <div class="modal lc-surface" :class="{ wide, xwide }">
        <header class="modal-head">
          <h2>{{ title }}</h2>
          <button class="icon-btn" @click="emit('close')" aria-label="Close">
            <AppIcon name="close" :size="16" />
          </button>
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
/* Surface (frost/rim/sheen) comes from the shared .lc-surface helper. */
.modal {
  width: 100%; max-width: 540px; animation: pop .2s ease;
}
.modal.wide { max-width: 880px; }
/* Grow to fit content up to a large cap, but never overflow the viewport. */
.modal.xwide { max-width: min(1240px, calc(100vw - 32px)); }
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

@media (max-width: 800px) {
  .overlay {
    z-index: 1000;
    align-items: flex-start;
    padding: 0;
  }
  .modal, .modal.wide, .modal.xwide {
    width: 100%;
    max-width: 100%;
    min-height: 100dvh;
    border-radius: 0;
    border: 0;
  }
  /* Full-bleed sheet: drop the rounded rim-light hairline. */
  .modal::before { display: none; }
  .modal-head {
    position: sticky; top: 0; z-index: 2;
    background: var(--lc-base-strong);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
  }
  .modal-body { padding: 16px 14px calc(80px + env(safe-area-inset-bottom)); }
}
</style>

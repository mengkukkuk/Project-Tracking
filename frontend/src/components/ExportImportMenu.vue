<script setup>
// Reusable Export(menu) + Import(file picker) cluster used by RecordList.vue
// and DashboardView.vue. The parent owns the export and import handlers — this
// component is purely UI: a button cluster with the format dropdown, the
// hidden file input, and click-outside-to-close behaviour.
import { ref, onMounted, onUnmounted, computed } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  // Allowed export formats, in display order. Examples: ['excel'], ['excel','pdf'].
  formats: { type: Array, default: () => ['excel', 'pdf'] },
  // Used to disable the Export button when there's nothing to emit. Pass -1
  // to mean "enabled but unknown count" (e.g. project-pack at page level).
  rows: { type: Number, default: 0 },
  // Show the Import button + hidden file input when true.
  importEnabled: { type: Boolean, default: false },
  // File-input accept attribute. Excel-only by default.
  accept: { type: String, default: '.xlsx,.xls' },
  // Disable the whole cluster (e.g. while project data hasn't loaded yet).
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['export', 'import-file'])

const menuOpen = ref(false)
const fileInput = ref(null)

const exportDisabled = computed(
  () => props.disabled || (props.rows !== -1 && props.rows === 0),
)

function toggleMenu() {
  if (exportDisabled.value) return
  menuOpen.value = !menuOpen.value
}
function closeMenu() {
  menuOpen.value = false
}
function chooseFormat(format) {
  closeMenu()
  emit('export', format)
}
function pickImportFile() {
  fileInput.value?.click()
}
function onFileChosen(e) {
  const file = e.target.files?.[0]
  if (file) emit('import-file', file)
  e.target.value = '' // allow re-picking the same file
}

onMounted(() => document.addEventListener('click', closeMenu))
onUnmounted(() => document.removeEventListener('click', closeMenu))
</script>

<template>
  <div class="eim" @click.stop>
    <div class="export-wrap">
      <button class="btn sm ghost" :disabled="exportDisabled" @click="toggleMenu">
        <AppIcon name="download" :size="14" />
        Export
      </button>
      <div v-if="menuOpen" class="export-menu lc-surface">
        <button v-if="formats.includes('excel')" @click="chooseFormat('excel')">
          Excel (.xlsx)
        </button>
        <button v-if="formats.includes('pdf')" @click="chooseFormat('pdf')">PDF</button>
        <button v-if="formats.includes('csv')" @click="chooseFormat('csv')">CSV</button>
      </div>
    </div>
    <template v-if="importEnabled">
      <button class="btn sm ghost" :disabled="disabled" @click="pickImportFile">Import</button>
      <input
        ref="fileInput"
        type="file"
        :accept="accept"
        class="hidden-file"
        @change="onFileChosen"
      />
    </template>
  </div>
</template>

<style scoped>
.eim { display: inline-flex; align-items: center; gap: 6px; }
.export-wrap { position: relative; }
/* Surface from .lc-surface; near-opaque base so the menu stays readable over
   whatever content sits behind it. */
.export-menu {
  --lc-base: var(--lc-base-strong);
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 20;
  padding: 4px; min-width: 140px; display: grid;
}
.export-menu button {
  text-align: left; background: none; border: none; cursor: pointer;
  font: inherit; color: var(--text); padding: 7px 10px; border-radius: 6px;
}
.export-menu button:hover { background: var(--bg-sunken); color: var(--accent); }
.hidden-file { display: none; }
</style>

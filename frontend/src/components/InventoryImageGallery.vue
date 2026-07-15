<script setup>
// Product-photo gallery for one inventory catalogue item. Owns the full
// authed-blob -> URL.createObjectURL -> revoke lifecycle: inventory image
// blobs are JWT-authed, so a bare <img src="/api/..."> would 401. Two modes:
//   - existing item (inventoryId set): fetch the list, blob each image into an
//     objectURL thumbnail; live upload/delete against the server.
//   - create mode (inventoryId === null): stage File objects locally with
//     preview objectURLs and surface them via update:pendingFiles; the parent
//     uploads them after the item is created (and thus has an id).
import { ref, watch, onBeforeUnmount } from 'vue'
import { api } from '@/api'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  inventoryId: { type: Number, default: null },
  editable: { type: Boolean, default: true },
  pendingFiles: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:pendingFiles', 'uploaded', 'error'])

const ui = useUiStore()
const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif'

// Existing-item thumbnails: [{ id, name, url }]. `url` is an objectURL we own.
const images = ref([])
// Create-mode staged files: [{ file, url }]. `url` is an objectURL we own.
const staged = ref([])
const loading = ref(false)
const busy = ref(false)
const fileInput = ref(null)
// Lightbox: url of the thumbnail currently shown full-size, or null when closed.
const previewUrl = ref(null)
// Natural (original, undistorted) pixel size of the image currently previewed.
const previewSize = ref(null)

function openPreview(url) {
  if (!url) return
  previewUrl.value = url
  previewSize.value = null
}
function closePreview() {
  previewUrl.value = null
  previewSize.value = null
}
function onPreviewLoad(ev) {
  previewSize.value = { w: ev.target.naturalWidth, h: ev.target.naturalHeight }
}

function revokeAll() {
  for (const im of images.value) if (im.url) URL.revokeObjectURL(im.url)
  for (const s of staged.value) if (s.url) URL.revokeObjectURL(s.url)
}

async function load() {
  if (props.inventoryId == null) return
  loading.value = true
  try {
    const { items } = await api.listInventoryImages(props.inventoryId)
    // Revoke the previous batch before replacing, so reloads don't leak.
    for (const im of images.value) if (im.url) URL.revokeObjectURL(im.url)
    const next = []
    for (const it of items) {
      try {
        const blob = await api.inventoryImageBlob(it.id)
        next.push({ id: it.id, name: it.name, url: URL.createObjectURL(blob) })
      } catch {
        next.push({ id: it.id, name: it.name, url: null })
      }
    }
    images.value = next
  } catch (e) {
    emit('error', e.message)
  } finally {
    loading.value = false
  }
}

function pickFiles() {
  fileInput.value?.click()
}

async function onFiles(ev) {
  const files = Array.from(ev.target.files || [])
  ev.target.value = '' // allow re-selecting the same file
  if (!files.length) return
  if (props.inventoryId == null) {
    // Create mode: stage locally, defer upload to the parent.
    for (const f of files) staged.value.push({ file: f, url: URL.createObjectURL(f) })
    emit('update:pendingFiles', staged.value.map((s) => s.file))
    return
  }
  // Existing item: upload live, then reload the strip.
  busy.value = true
  try {
    const { items } = await api.uploadInventoryImages(props.inventoryId, files)
    await load()
    ui.success(`Uploaded ${items.length} image(s)`)
    emit('uploaded', items)
  } catch (e) {
    ui.error(e.message)
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}

async function removeExisting(im) {
  if (!window.confirm(`Delete image "${im.name}"?`)) return
  busy.value = true
  try {
    await api.deleteInventoryImage(im.id)
    if (im.url) URL.revokeObjectURL(im.url)
    images.value = images.value.filter((x) => x.id !== im.id)
  } catch (e) {
    ui.error(e.message)
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}

function removeStaged(idx) {
  const [s] = staged.value.splice(idx, 1)
  if (s?.url) URL.revokeObjectURL(s.url)
  emit('update:pendingFiles', staged.value.map((x) => x.file))
}

watch(() => props.inventoryId, load, { immediate: true })
onBeforeUnmount(revokeAll)
</script>

<template>
  <div class="gallery">
    <div class="strip">
      <template v-if="inventoryId != null">
        <figure v-for="im in images" :key="im.id" class="thumb">
          <img
            v-if="im.url"
            :src="im.url"
            :alt="im.name"
            class="clickable"
            @click="openPreview(im.url)"
          />
          <span v-else class="broken">?</span>
          <button
            v-if="editable"
            type="button"
            class="del"
            title="Delete image"
            :disabled="busy"
            @click="removeExisting(im)"
          >×</button>
        </figure>
      </template>
      <template v-else>
        <figure v-for="(s, i) in staged" :key="i" class="thumb">
          <img :src="s.url" :alt="s.file.name" class="clickable" @click="openPreview(s.url)" />
          <button
            type="button"
            class="del"
            title="Remove"
            @click="removeStaged(i)"
          >×</button>
        </figure>
      </template>

      <button
        v-if="editable"
        type="button"
        class="add"
        :disabled="busy"
        title="Add image(s)"
        @click="pickFiles"
      >
        <span v-if="busy">…</span>
        <span v-else>+</span>
      </button>
      <span
        v-if="!images.length && !staged.length && !editable"
        class="empty"
      >No images</span>
    </div>

    <input
      ref="fileInput"
      type="file"
      :accept="ACCEPT"
      multiple
      hidden
      @change="onFiles"
    />

    <Teleport to="body">
      <div v-if="previewUrl" class="lightbox" @click="closePreview">
        <button type="button" class="lightbox-close" title="Close" @click.stop="closePreview">×</button>
        <figure class="lightbox-figure" @click.stop>
          <img :src="previewUrl" alt="" @load="onPreviewLoad" />
          <figcaption v-if="previewSize">{{ previewSize.w }} × {{ previewSize.h }} px</figcaption>
        </figure>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.gallery { display: grid; gap: 8px; }
.strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.thumb {
  position: relative;
  width: 64px;
  height: 64px;
  margin: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--bg-sunken);
}
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb img.clickable { cursor: zoom-in; }
.broken {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--text-dim);
  font-weight: 800;
}
.del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  line-height: 1;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, .6);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.del:disabled { opacity: .5; cursor: not-allowed; }
.add {
  width: 64px;
  height: 64px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text-dim);
  font-size: 24px;
  cursor: pointer;
}
.add:disabled { opacity: .6; cursor: not-allowed; }
.add:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.empty { color: var(--text-dim); font-size: 12px; }
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, .8);
  cursor: zoom-out;
}
.lightbox-figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: default;
}
.lightbox-figure img {
  max-width: 90vw;
  max-height: 85vh;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, .5);
}
.lightbox-figure figcaption {
  color: rgba(255, 255, 255, .75);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.lightbox-close {
  position: absolute;
  top: 16px;
  right: 20px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, .15);
  color: #fff;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}
.lightbox-close:hover { background: rgba(255, 255, 255, .3); }
</style>

<script setup>
// Configurable shimmer block — the atomic unit of the skeleton system.
// Purely presentational; composed by RouteSkeleton.vue and used directly in
// ProjectDetail.vue. The shimmer + reduced-motion behaviour live on the
// global `.skeleton` classes in assets/main.css.
import { computed } from 'vue'

const props = defineProps({
  w: { type: [String, Number], default: '100%' },
  h: { type: [String, Number], default: '14px' },
  radius: { type: [String, Number], default: null },
  // text | title | chip | circle | block
  variant: { type: String, default: 'block' },
})

const size = (v) => (typeof v === 'number' ? `${v}px` : v)

const style = computed(() => {
  const s = { width: size(props.w), height: size(props.h) }
  if (props.radius != null) s.borderRadius = size(props.radius)
  return s
})
</script>

<template>
  <div class="skeleton" :class="`skeleton-${variant}`" :style="style" />
</template>

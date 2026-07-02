<script setup>
import { computed } from 'vue'
import { GRADE_COLORS } from '@/utils/summaryCalc'

const props = defineProps({ grade: { type: String, required: true } })
const color = computed(() => GRADE_COLORS[props.grade] || GRADE_COLORS.D)
</script>

<template>
  <div
    class="grade-chip"
    :style="{ color, borderColor: color, backgroundColor: `${color}1a` }"
  >
    {{ grade }}
  </div>
</template>

<style scoped>
.grade-chip {
  width: 44px; height: 44px;
  border-radius: 10px;
  border: 2px solid;
  display: grid; place-items: center;
  font-size: 19px; font-weight: 700;
}
</style>

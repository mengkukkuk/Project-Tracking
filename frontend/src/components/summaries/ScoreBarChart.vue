<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '@/composables/useChartTheme'
import { SUMMARY_COLORS } from '@/utils/summaryCalc'

use([BarChart, TooltipComponent, GridComponent, CanvasRenderer])

const props = defineProps({
  results: {
    type: Object,
    required: true, // { roiScore, healthScore, performanceRating, safety }
  },
})
const theme = useChartTheme()

const CATEGORIES = ['ROI', 'Health', 'Performance', 'Safety']

const option = computed(() => ({
  tooltip: {
    trigger: 'axis', axisPointer: { type: 'shadow' },
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  grid: { left: 32, right: 12, top: 12, bottom: 24 },
  xAxis: {
    type: 'category',
    data: CATEGORIES,
    axisLine: { lineStyle: { color: theme.value.axis } },
    axisLabel: { color: theme.value.text, fontSize: 11 },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    axisLabel: { color: theme.value.text, fontSize: 11 },
    splitLine: { lineStyle: { color: theme.value.split } },
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 36,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      data: [
        { value: Math.round(props.results.roiScore), itemStyle: { color: SUMMARY_COLORS.roi } },
        { value: Math.round(props.results.healthScore), itemStyle: { color: SUMMARY_COLORS.health } },
        { value: Math.round(props.results.performanceRating), itemStyle: { color: SUMMARY_COLORS.performance } },
        { value: Math.round(props.results.safety), itemStyle: { color: SUMMARY_COLORS.safety } },
      ],
    },
  ],
}))
</script>

<template>
  <div class="card chart-card">
    <h4 class="card-title">Final Score Breakdown</h4>
    <v-chart class="chart" theme="macarons" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 16px; }
.card-title { font-size: 13px; font-weight: 700; color: var(--text); margin: 0 0 8px; }
.chart { height: 160px; }
</style>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '@/composables/useChartTheme'
import { SUMMARY_COLORS } from '@/utils/summaryCalc'

use([BarChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const props = defineProps({
  rows: { type: Array, default: () => [] }, // [{ name, performance, roi, health }]
})
const theme = useChartTheme()

function truncate(name) {
  return name.length > 14 ? `${name.slice(0, 13)}…` : name
}

const option = computed(() => ({
  tooltip: {
    trigger: 'axis', axisPointer: { type: 'shadow' },
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11, color: theme.value.text } },
  grid: { left: 36, right: 12, top: 16, bottom: 60 },
  xAxis: {
    type: 'category',
    data: props.rows.map((r) => truncate(r.name)),
    axisLine: { lineStyle: { color: theme.value.axis } },
    axisLabel: { color: theme.value.text, fontSize: 10, rotate: 30 },
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
    { name: 'Performance', type: 'bar', barMaxWidth: 14, itemStyle: { color: SUMMARY_COLORS.performance, borderRadius: [2, 2, 0, 0] }, data: props.rows.map((r) => Math.round(r.performance)) },
    { name: 'ROI', type: 'bar', barMaxWidth: 14, itemStyle: { color: SUMMARY_COLORS.roi, borderRadius: [2, 2, 0, 0] }, data: props.rows.map((r) => Math.round(r.roi)) },
    { name: 'Health', type: 'bar', barMaxWidth: 14, itemStyle: { color: SUMMARY_COLORS.health, borderRadius: [2, 2, 0, 0] }, data: props.rows.map((r) => Math.round(r.health)) },
  ],
}))
</script>

<template>
  <div class="card chart-card">
    <h4 class="card-title">All Projects — Final Results Comparison</h4>
    <p class="card-subtitle">Performance, ROI &amp; Health scores across all projects</p>
    <v-chart class="chart" theme="macarons" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 18px; }
.card-title { font-size: 14px; font-weight: 700; color: var(--text); margin: 0; }
.card-subtitle { font-size: 12px; color: var(--text-dim); margin: 2px 0 8px; }
.chart { height: 220px; }
</style>

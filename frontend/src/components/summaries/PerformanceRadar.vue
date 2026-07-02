<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '@/composables/useChartTheme'

use([RadarChart, TooltipComponent, RadarComponent, CanvasRenderer])

const props = defineProps({
  results: { type: Object, required: true },   // { roiScore, healthScore, performanceRating, safety }
  efficiency: { type: Number, required: true }, // efficiencyAxis(metrics)
  color: { type: String, default: '#6366f1' },
})
const theme = useChartTheme()

const option = computed(() => ({
  tooltip: {
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  radar: {
    indicator: [
      { name: 'ROI', max: 100 },
      { name: 'Health', max: 100 },
      { name: 'Performance', max: 100 },
      { name: 'Safety', max: 100 },
      { name: 'Efficiency', max: 100 },
    ],
    radius: '68%',
    axisName: { color: theme.value.text, fontSize: 10 },
    splitLine: { lineStyle: { color: theme.value.split } },
    splitArea: { show: false },
    axisLine: { lineStyle: { color: theme.value.axis } },
  },
  series: [
    {
      type: 'radar',
      areaStyle: { color: props.color, opacity: 0.15 },
      lineStyle: { color: props.color, width: 2 },
      itemStyle: { color: props.color },
      data: [
        {
          value: [
            Math.round(props.results.roiScore),
            Math.round(props.results.healthScore),
            Math.round(props.results.performanceRating),
            Math.round(props.results.safety),
            Math.round(props.efficiency),
          ],
        },
      ],
    },
  ],
}))
</script>

<template>
  <div class="card chart-card">
    <h4 class="card-title">Performance Radar</h4>
    <v-chart class="chart" theme="macarons" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 16px; }
.card-title { font-size: 13px; font-weight: 700; color: var(--text); margin: 0 0 8px; }
.chart { height: 160px; }
</style>

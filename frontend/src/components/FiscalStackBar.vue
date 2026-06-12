<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { STAGES } from '@/stores/projects'
import { STAGE_COLORS, useChartTheme } from '@/composables/useChartTheme'
import { useFormat } from '@/composables/useFormat'

use([BarChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const props = defineProps({ breakdown: { type: Array, default: () => [] } })
const { fy } = useFormat()
const theme = useChartTheme()

const option = computed(() => ({
  tooltip: {
    trigger: 'axis', axisPointer: { type: 'shadow' },
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11, color: theme.value.text } },
  grid: { left: 70, right: 16, top: 16, bottom: 44 },
  xAxis: {
    type: 'value',
    axisLabel: { color: theme.value.text },
    splitLine: { lineStyle: { color: theme.value.split } },
  },
  yAxis: {
    type: 'category',
    data: props.breakdown.map((b) => fy(b.fy)),
    axisLine: { show: false }, axisTick: { show: false },
    axisLabel: { color: theme.value.text },
  },
  series: STAGES.map((stage) => ({
    name: stage,
    type: 'bar',
    stack: 'total',
    itemStyle: { color: STAGE_COLORS[stage] },
    data: props.breakdown.map((b) => b[stage]),
  })),
}))
</script>

<template>
  <div class="card chart-card">
    <h3 class="card-title">โครงการแยกตามปีงบประมาณ</h3>
    <v-chart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 18px; }
.card-title { font-size: 13px; font-weight: 600; color: var(--text); margin: 0 0 8px; }
.chart { height: 280px; }
</style>

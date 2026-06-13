<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '@/composables/useChartTheme'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ data: { type: Array, default: () => [] } })
const theme = useChartTheme()

const option = computed(() => ({
  tooltip: {
    trigger: 'item', formatter: '{b}: {c} ({d}%)',
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11, color: theme.value.text } },
  series: [
    {
      type: 'pie',
      radius: ['46%', '70%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: theme.value.tooltipBg, borderWidth: 2, borderRadius: 4 },
      label: { show: false },
      data: props.data.map((d) => ({
        name: d.name,
        value: d.value,
      })),
    },
  ],
}))
</script>

<template>
  <div class="card chart-card">
    <h3 class="card-title">สัดส่วนตามกลุ่มงาน</h3>
    <v-chart class="chart" theme="macarons" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 18px; }
.card-title { font-size: 13px; font-weight: 600; color: var(--text); margin: 0 0 8px; }
.chart { height: 280px; }
</style>

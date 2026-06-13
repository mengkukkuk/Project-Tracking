<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { FunnelChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '@/composables/useChartTheme'

use([FunnelChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ funnel: { type: Array, default: () => [] } })
const theme = useChartTheme()

const option = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} โครงการ',
    backgroundColor: theme.value.tooltipBg,
    borderColor: theme.value.tooltipBorder,
    textStyle: { color: theme.value.text },
  },
  series: [
    {
      type: 'funnel',
      left: '5%', right: '5%', top: 10, bottom: 10,
      minSize: '24%', maxSize: '100%', sort: 'none', gap: 4,
      label: { show: true, position: 'inside', color: '#fff', fontWeight: 600, fontSize: 12 },
      labelLine: { show: false },
      itemStyle: { borderRadius: 5, borderWidth: 0 },
      emphasis: { label: { fontSize: 13 } },
      data: props.funnel.map((f) => ({
        name: f.stage,
        value: f.count,
      })),
    },
  ],
}))
</script>

<template>
  <div class="card chart-card">
    <h3 class="card-title">Pipeline ตามขั้นตอน</h3>
    <v-chart class="chart" theme="macarons" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-card { padding: 18px; }
.card-title { font-size: 13px; font-weight: 600; color: var(--text); margin: 0 0 8px; }
.chart { height: 280px; }
</style>

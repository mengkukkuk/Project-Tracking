import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'

// ECharts renders to canvas and can't read CSS custom properties, so chart
// axis/grid/text colors are resolved here from the active theme instead.
export const STAGE_COLORS = {
  'Pre-Sale': '#f59e0b',
  'Project Initiation': '#3b82f6',
  Award: '#8b5cf6',
  'Project Delivery': '#14b8a6',
  Completed: '#10b981',
}

export const DOMAIN_COLORS = {
  'Vision Sensor': '#06b6d4',
  Robot: '#f43f5e',
  PLC: '#f59e0b',
  IoT: '#8b5cf6',
  AI: '#10b981',
}

export const PRIORITY_COLORS = {
  low: '#64748b',
  medium: '#3b82f6',
  high: '#f59e0b',
  critical: '#ef4444',
}

export function useChartTheme() {
  const ui = useUiStore()
  return computed(() => {
    const dark = ui.isDark
    return {
      text: dark ? '#cbd5e1' : '#475569',
      axis: dark ? '#334155' : '#e2e8f0',
      split: dark ? '#1e293b' : '#eef2f7',
      tooltipBg: dark ? '#1e293b' : '#ffffff',
      tooltipBorder: dark ? '#334155' : '#e2e8f0',
    }
  })
}

<script setup>
import { computed } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import KpiCard from '@/components/KpiCard.vue'
import FunnelChart from '@/components/FunnelChart.vue'
import FiscalStackBar from '@/components/FiscalStackBar.vue'
import DomainDonut from '@/components/DomainDonut.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const store = useProjectsStore()
const { baht, date, daysUntil } = useFormat()

const s = computed(() => store.stats || {})

function dueLabel(iso) {
  const d = daysUntil(iso)
  if (d == null) return ''
  return d < 0 ? `เกินกำหนด ${-d} วัน` : `อีก ${d} วัน`
}
</script>

<template>
  <div class="view">
    <header class="top">
      <h1 class="page-title">ภาพรวมโครงการ</h1>
      <span class="muted">อัปเดตล่าสุด · {{ new Date().toLocaleDateString('th-TH') }}</span>
    </header>

    <div class="kpi-grid">
      <KpiCard label="จำนวนโครงการ" :value="s.totalProjects ?? 0" icon="▦" accent="#14b8a6" />
      <KpiCard label="มูลค่ารวม" :value="baht(s.totalValue)" icon="฿" accent="#3b82f6" />
      <KpiCard label="มูลค่า Pipeline" :value="baht(s.pipelineValue)" icon="◔" accent="#f59e0b" />
      <KpiCard label="อยู่ระหว่างส่งมอบ" :value="s.inDelivery ?? 0" icon="⇄" accent="#8b5cf6" />
      <KpiCard label="เสร็จสิ้น" :value="`${s.completed ?? 0}`" :sub="`${s.completionRate ?? 0}% ของทั้งหมด`" icon="✓" accent="#10b981" />
      <KpiCard label="เกินกำหนด" :value="s.overdue ?? 0" :sub="`เฉลี่ยคืบหน้า ${s.avgProgress ?? 0}%`" icon="⚠" accent="#ef4444" />
    </div>

    <div class="chart-grid">
      <FunnelChart :funnel="store.funnel" />
      <FiscalStackBar :breakdown="store.fiscalBreakdown" />
    </div>

    <div class="chart-grid">
      <DomainDonut :data="store.domainBreakdown" />

      <div class="card upcoming">
        <h3 class="card-title">⏱ ใกล้ถึงกำหนด / เกินกำหนด</h3>
        <ul v-if="s.upcoming?.length" class="up-list">
          <li v-for="p in s.upcoming" :key="p.id" @click="store.openDetail(p.id)">
            <div class="up-main">
              <div class="up-name">{{ p.name }}</div>
              <StatusBadge :status="p.status" />
            </div>
            <div class="up-meta">
              <span class="mono">{{ baht(p.value) }}</span>
              <span class="due" :class="{ over: daysUntil(p.dueDate) < 0 }">
                {{ date(p.dueDate) }} · {{ dueLabel(p.dueDate) }}
              </span>
            </div>
          </li>
        </ul>
        <p v-else class="empty">ไม่มีโครงการที่ใกล้ถึงกำหนด 🎉</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin-bottom: 16px; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
@media (max-width: 900px) { .chart-grid { grid-template-columns: 1fr; } }
.card-title { font-size: 13px; font-weight: 600; color: var(--text); margin: 0 0 12px; }
.upcoming { padding: 18px; }
.up-list { list-style: none; display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto; }
.up-list li { padding: 10px 12px; border-radius: 9px; background: var(--bg-sunken); cursor: pointer; transition: background .12s; }
.up-list li:hover { background: var(--border); }
.up-main { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.up-name { font-size: 13px; font-weight: 500; color: var(--text); }
.up-meta { display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px; color: var(--text-dim); }
.due.over { color: #ef4444; font-weight: 600; }
.empty { color: var(--text-dim); font-size: 13px; padding: 30px; text-align: center; }
</style>

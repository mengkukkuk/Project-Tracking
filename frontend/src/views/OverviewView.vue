<script setup>
import { computed } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import KpiCard from '@/components/KpiCard.vue'
import FunnelChart from '@/components/FunnelChart.vue'
import FiscalStackBar from '@/components/FiscalStackBar.vue'
import DomainDonut from '@/components/DomainDonut.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import PriorityBadge from '@/components/PriorityBadge.vue'
import ProjectFilters from '@/components/ProjectFilters.vue'
import AppIcon from '@/components/AppIcon.vue'

const store = useProjectsStore()
const { baht, date, daysUntil } = useFormat()

const s = computed(() => store.stats || {})

const attention = computed(() => {
  return store.projects
    .map((p) => {
      const due = daysUntil(p.dueDate)
      let reason = ''
      let weight = 0
      if (due != null && due < 0 && p.status !== 'Completed') {
        reason = `Overdue by ${Math.abs(due)} day${Math.abs(due) === 1 ? '' : 's'}`
        weight = 100 + Math.abs(due)
      } else if (due != null && due <= 7 && p.status !== 'Completed') {
        reason = `Due in ${due} day${due === 1 ? '' : 's'}`
        weight = 80 - due
      } else if (p.priority === 'critical' && p.status !== 'Completed') {
        reason = 'Critical priority'
        weight = 70
      } else if ((p.value || 0) >= 1000000 && p.status !== 'Completed') {
        reason = 'High-value pipeline'
        weight = 50
      }
      return { ...p, due, reason, weight }
    })
    .filter((p) => p.reason)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 6)
})

const riskCounts = computed(() => {
  let overdue = 0
  let dueSoon = 0
  let critical = 0
  for (const p of store.projects) {
    const due = daysUntil(p.dueDate)
    if (p.status !== 'Completed' && due != null && due < 0) overdue += 1
    if (p.status !== 'Completed' && due != null && due >= 0 && due <= 7) dueSoon += 1
    if (p.status !== 'Completed' && p.priority === 'critical') critical += 1
  }
  return { overdue, dueSoon, critical }
})

function dueLabel(iso) {
  const d = daysUntil(iso)
  if (d == null) return ''
  if (d < 0) return `overdue ${-d}d`
  if (d === 0) return 'due today'
  return `${d}d left`
}
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Command center</div>
        <h1 class="page-title">Project overview</h1>
        <p class="page-subtitle">A focused view of delivery health, pipeline value, and projects that need attention.</p>
      </div>
      <span class="updated">Updated {{ new Date().toLocaleDateString('en-GB') }}</span>
    </header>

    <ProjectFilters />

    <div class="kpi-grid">
      <KpiCard label="Projects" :value="s.totalProjects ?? 0" icon="overview" accent="#14b8a6" />
      <KpiCard label="Total value" :value="baht(s.totalValue)" icon="money" accent="#3b82f6" />
      <KpiCard label="Pipeline value" :value="baht(s.pipelineValue)" icon="target" accent="#f59e0b" />
      <KpiCard label="In delivery" :value="s.inDelivery ?? 0" icon="kanban" accent="#8b5cf6" actionable @click="store.setFilter({ status: 'Project Delivery' })" />
      <KpiCard label="Completed" :value="`${s.completed ?? 0}`" :sub="`${s.completionRate ?? 0}% complete`" icon="check" accent="#10b981" actionable @click="store.setFilter({ status: 'Completed' })" />
      <KpiCard label="Overdue" :value="riskCounts.overdue" :sub="`${riskCounts.dueSoon} due this week`" icon="alert" accent="#ef4444" />
    </div>

    <section class="attention card">
      <div class="section-head">
        <div>
          <h2>Needs attention</h2>
          <p>Sorted by due risk, critical priority, then high-value work.</p>
        </div>
        <div class="risk-strip">
          <span><AppIcon name="alert" :size="14" /> {{ riskCounts.overdue }} overdue</span>
          <span><AppIcon name="clock" :size="14" /> {{ riskCounts.dueSoon }} due soon</span>
          <span><AppIcon name="target" :size="14" /> {{ riskCounts.critical }} critical</span>
        </div>
      </div>

      <div v-if="attention.length" class="attention-list">
        <button v-for="p in attention" :key="p.id" type="button" class="attention-row" @click="store.openDetail(p.id)">
          <span class="reason" :class="{ danger: p.due < 0, warn: p.due >= 0 && p.due <= 7 }">{{ p.reason }}</span>
          <span class="project">
            <strong>{{ p.name }}</strong>
            <small>{{ p.customer || 'No customer' }} · {{ p.pm || 'No PM' }}</small>
          </span>
          <StatusBadge :status="p.status" />
          <PriorityBadge :priority="p.priority" />
          <span class="money mono">{{ baht(p.value) }}</span>
          <span class="due">{{ date(p.dueDate) }}</span>
        </button>
      </div>
      <div v-else class="empty-state">
        <AppIcon name="check" :size="22" />
        No urgent projects in the current view.
      </div>
    </section>

    <div class="chart-grid">
      <FunnelChart :funnel="store.funnel" />
      <FiscalStackBar :breakdown="store.fiscalBreakdown" />
    </div>

    <div class="chart-grid">
      <DomainDonut :data="store.domainBreakdown" />

      <div class="card upcoming">
        <h3 class="card-title"><AppIcon name="calendar" :size="15" /> Upcoming / overdue</h3>
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
        <p v-else class="empty">No upcoming deadlines.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.updated {
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 700;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin-bottom: 16px; }
.attention {
  padding: 16px;
  margin-bottom: 16px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}
.section-head h2 {
  font-size: 15px;
  margin: 0;
}
.section-head p {
  color: var(--text-dim);
  font-size: 12px;
  margin-top: 3px;
}
.risk-strip {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.risk-strip span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-dim);
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 8px;
  font-size: 12px;
  font-weight: 700;
}
.attention-list {
  display: grid;
  gap: 7px;
}
.attention-row {
  display: grid;
  grid-template-columns: minmax(120px, .8fr) minmax(220px, 1.4fr) auto auto minmax(74px, auto) minmax(82px, auto);
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.attention-row:hover {
  border-color: var(--accent);
  background: var(--bg-sunken);
}
.reason {
  justify-self: start;
  color: var(--info);
  background: color-mix(in srgb, var(--info) 10%, var(--surface));
  border-radius: 7px;
  padding: 4px 7px;
  font-size: 11px;
  font-weight: 700;
}
.reason.danger {
  color: var(--danger);
  background: var(--critical-bg);
}
.reason.warn {
  color: var(--warning);
  background: var(--warning-bg);
}
.project {
  display: grid;
  min-width: 0;
}
.project strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.project small {
  color: var(--text-dim);
  font-size: 11px;
  margin-top: 2px;
}
.money,
.due {
  color: var(--text-dim);
  font-size: 12px;
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 74px;
  color: var(--text-dim);
  background: var(--bg-sunken);
  border: 1px dashed var(--border);
  border-radius: 8px;
  font-size: 13px;
}
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.card-title { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 700; color: var(--text); margin: 0 0 12px; }
.upcoming { padding: 18px; }
.up-list { list-style: none; display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto; }
.up-list li { padding: 10px 12px; border-radius: 8px; background: var(--bg-sunken); cursor: pointer; transition: background .12s; }
.up-list li:hover { background: var(--border); }
.up-main { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.up-name { font-size: 13px; font-weight: 600; color: var(--text); }
.up-meta { display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px; color: var(--text-dim); gap: 12px; }
.due.over { color: var(--danger); font-weight: 700; }
.empty { color: var(--text-dim); font-size: 13px; padding: 30px; text-align: center; }

@media (max-width: 1000px) {
  .chart-grid { grid-template-columns: 1fr; }
  .attention-row { grid-template-columns: 1fr auto; }
  .attention-row > :nth-child(n+3) { justify-self: start; }
}
@media (max-width: 720px) {
  .section-head { display: grid; }
  .risk-strip { justify-content: flex-start; }
  .attention-row { grid-template-columns: 1fr; }
}
</style>

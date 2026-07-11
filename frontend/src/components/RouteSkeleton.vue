<script setup>
// Route-aware loading skeleton. Composes SkeletonBlock into layouts that
// mirror each real view's geometry so the transition from placeholder to
// content is seamless (no reflow jump). Consumed by App.vue's loading gate
// (variant resolved from the route) and DashboardView.vue.
import SkeletonBlock from './SkeletonBlock.vue'

defineProps({
  // overview | table | bom | dashboard | summaries | board | generic
  variant: { type: String, default: 'generic' },
})

const rows = (n) => Array.from({ length: n })
</script>

<template>
  <div class="route-skeleton">
    <!-- Masthead: every view has a title + subtitle line -->
    <div class="sk-head">
      <SkeletonBlock w="42%" h="22px" variant="title" />
      <SkeletonBlock w="26%" h="12px" variant="text" />
    </div>

    <!-- OVERVIEW: KPI row + attention list + two chart cards -->
    <template v-if="variant === 'overview'">
      <div class="sk-kpis">
        <div v-for="(_, i) in rows(6)" :key="i" class="card sk-card sk-kpi">
          <SkeletonBlock w="40px" h="40px" variant="circle" />
          <div class="sk-stack">
            <SkeletonBlock w="60%" h="10px" variant="text" />
            <SkeletonBlock w="80%" h="20px" variant="title" />
          </div>
        </div>
      </div>
      <div class="card sk-card">
        <SkeletonBlock w="30%" h="16px" variant="title" />
        <div v-for="(_, i) in rows(4)" :key="i" class="sk-line">
          <SkeletonBlock w="18%" h="22px" variant="chip" />
          <SkeletonBlock w="45%" h="12px" variant="text" />
          <SkeletonBlock w="12%" h="12px" variant="text" />
        </div>
      </div>
      <div class="sk-charts">
        <div class="card sk-card sk-chart"><SkeletonBlock w="100%" h="220px" radius="10px" /></div>
        <div class="card sk-card sk-chart"><SkeletonBlock w="100%" h="220px" radius="10px" /></div>
      </div>
    </template>

    <!-- TABLE / BOM: filter bar + ledger rows -->
    <template v-else-if="variant === 'table' || variant === 'bom'">
      <div class="card sk-card sk-filters">
        <SkeletonBlock v-for="(_, i) in rows(4)" :key="i" w="120px" h="34px" radius="8px" />
      </div>
      <div class="card sk-card sk-ledger">
        <div v-for="(_, i) in rows(9)" :key="i" class="sk-row">
          <SkeletonBlock w="8%" h="12px" variant="text" />
          <SkeletonBlock w="28%" h="12px" variant="text" />
          <SkeletonBlock w="16%" h="22px" variant="chip" />
          <SkeletonBlock w="14%" h="12px" variant="text" />
          <SkeletonBlock w="12%" h="12px" variant="text" />
        </div>
      </div>
    </template>

    <!-- DASHBOARD: summary header + section cards + step rows -->
    <template v-else-if="variant === 'dashboard'">
      <div class="card sk-card">
        <SkeletonBlock w="45%" h="20px" variant="title" />
        <div class="sk-line">
          <SkeletonBlock w="20%" h="22px" variant="chip" />
          <SkeletonBlock w="20%" h="22px" variant="chip" />
          <SkeletonBlock w="20%" h="22px" variant="chip" />
        </div>
      </div>
      <div class="sk-sections">
        <div v-for="(_, i) in rows(2)" :key="i" class="card sk-card">
          <SkeletonBlock w="35%" h="16px" variant="title" />
          <SkeletonBlock w="100%" h="12px" variant="text" />
          <SkeletonBlock w="85%" h="12px" variant="text" />
          <SkeletonBlock w="70%" h="12px" variant="text" />
        </div>
      </div>
      <div class="card sk-card">
        <SkeletonBlock w="30%" h="16px" variant="title" />
        <div v-for="(_, i) in rows(5)" :key="i" class="sk-row">
          <SkeletonBlock w="10%" h="12px" variant="text" />
          <SkeletonBlock w="40%" h="12px" variant="text" />
          <SkeletonBlock w="18%" h="12px" variant="text" />
          <SkeletonBlock w="16%" h="22px" variant="chip" />
        </div>
      </div>
    </template>

    <!-- SUMMARIES: stepper + input rows + ring gauges -->
    <template v-else-if="variant === 'summaries'">
      <div class="card sk-card sk-filters">
        <SkeletonBlock v-for="(_, i) in rows(4)" :key="i" w="90px" h="30px" radius="999px" />
      </div>
      <div class="card sk-card">
        <SkeletonBlock w="30%" h="16px" variant="title" />
        <div v-for="(_, i) in rows(4)" :key="i" class="sk-line">
          <SkeletonBlock w="30%" h="12px" variant="text" />
          <SkeletonBlock w="55%" h="34px" radius="8px" />
        </div>
      </div>
      <div class="sk-rings">
        <div v-for="(_, i) in rows(4)" :key="i" class="card sk-card sk-ring">
          <SkeletonBlock w="110px" h="110px" variant="circle" />
        </div>
      </div>
    </template>

    <!-- BOARD (pipeline / pm-cards): columns of stacked mini-cards -->
    <template v-else-if="variant === 'board'">
      <div class="sk-board">
        <div v-for="(_, c) in rows(4)" :key="c" class="sk-col">
          <SkeletonBlock w="60%" h="14px" variant="text" />
          <div v-for="(_, i) in rows(3)" :key="i" class="card sk-card sk-mini">
            <SkeletonBlock w="80%" h="14px" variant="text" />
            <SkeletonBlock w="50%" h="22px" variant="chip" />
          </div>
        </div>
      </div>
    </template>

    <!-- GENERIC fallback -->
    <template v-else>
      <div v-for="(_, i) in rows(3)" :key="i" class="card sk-card">
        <SkeletonBlock w="40%" h="16px" variant="title" />
        <SkeletonBlock w="100%" h="12px" variant="text" />
        <SkeletonBlock w="75%" h="12px" variant="text" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.route-skeleton { display: flex; flex-direction: column; gap: 16px; }
.sk-head { display: flex; flex-direction: column; gap: 8px; margin-bottom: 2px; }
.sk-stack { display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 0; }
.sk-line { display: flex; align-items: center; gap: 10px; }
.sk-row { display: flex; align-items: center; gap: 12px; }

.sk-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
.sk-kpi { flex-direction: row; align-items: center; gap: 12px; }

.sk-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.sk-filters { flex-direction: row; flex-wrap: wrap; gap: 10px; }
.sk-ledger { gap: 14px; }

.sk-sections { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.sk-rings { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.sk-ring { align-items: center; }

.sk-board { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.sk-col { display: flex; flex-direction: column; gap: 10px; }
.sk-mini { gap: 8px; }

@media (max-width: 760px) {
  .sk-charts,
  .sk-sections { grid-template-columns: 1fr; }
  .sk-rings { grid-template-columns: 1fr 1fr; }
  .sk-board { grid-template-columns: 1fr; }
  .sk-ledger .sk-row > :nth-child(n + 4) { display: none; }
}
</style>

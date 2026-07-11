<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import { DOMAIN_COLORS } from '@/composables/useChartTheme'
import AppIcon from '@/components/AppIcon.vue'
import GradeChip from '@/components/summaries/GradeChip.vue'
import RingGauge from '@/components/summaries/RingGauge.vue'
import MetricRow from '@/components/summaries/MetricRow.vue'
import ScoreBarChart from '@/components/summaries/ScoreBarChart.vue'
import PerformanceRadar from '@/components/summaries/PerformanceRadar.vue'
import ProjectsCompareChart from '@/components/summaries/ProjectsCompareChart.vue'
import {
  summarize,
  seedTeamSize,
  seedComplexity,
  derivedDurationWeeks,
  computeMetrics,
  computeResults,
  gradeFor,
  efficiencyAxis,
  SUMMARY_COLORS,
} from '@/utils/summaryCalc'

const store = useProjectsStore()
const ui = useUiStore()
const { baht } = useFormat()

const flowSteps = [
  { step: 1, icon: 'target', label: 'Project Name' },
  { step: 2, icon: 'money', label: 'Input Boxes' },
  { step: 3, icon: 'activity', label: 'Calculated Metrics' },
  { step: 4, icon: 'check', label: 'Final Results' },
]

const selectedId = ref(null)
const selectedProject = computed(
  () => store.projects.find((p) => p.id === selectedId.value) || store.projects[0] || null,
)

watch(
  () => store.projects,
  (list) => {
    if (!selectedId.value && list.length) selectedId.value = list[0].id
  },
  { immediate: true },
)

// Local editable "what-if" inputs for the selected project's pipeline.
const inputs = reactive({ budget: 0, teamSize: 1, durationWeeks: 12, complexity: 5 })
// Fields present here get flushed as a single debounced PATCH; durationWeeks
// is a what-if-only input derived from dates and is never persisted.
const dirty = reactive({})
const FIELD_MAP = { budget: 'value', teamSize: 'teamSize', complexity: 'complexity' }
const saveState = ref('idle') // idle | saving | saved
let saveTimer = null

// Tracks which project id `inputs`/`dirty` currently belong to. Needed
// because `selectedProject` has already moved on to the new project by the
// time the switch-away watcher below runs — flushSave must target the id
// the dirty patch was collected for, not whatever is selected right now.
const currentPid = ref(null)

function hydrateInputs(p) {
  currentPid.value = p?.id ?? null
  inputs.budget = p?.value || 0
  inputs.teamSize = seedTeamSize(p)
  inputs.durationWeeks = derivedDurationWeeks(p)
  inputs.complexity = seedComplexity(p)
}

watch(
  selectedProject,
  (p, prev) => {
    if (prev) {
      clearTimeout(saveTimer)
      flushSave(prev.id)
    }
    hydrateInputs(p)
  },
  { immediate: true },
)

const metrics = computed(() => computeMetrics(inputs))
const results = computed(() => computeResults(metrics.value, inputs))
const grade = computed(() => gradeFor(results.value.performanceRating))
const efficiency = computed(() => efficiencyAxis(metrics.value))

function resetDuration() {
  if (selectedProject.value) inputs.durationWeeks = derivedDurationWeeks(selectedProject.value)
}

function setInput(key, raw) {
  inputs[key] = Number.isFinite(raw) ? raw : 0
  if (!(key in FIELD_MAP)) return
  dirty[FIELD_MAP[key]] = inputs[key]
  clearTimeout(saveTimer)
  saveState.value = 'saving'
  saveTimer = setTimeout(() => flushSave(currentPid.value), 600)
}

async function flushSave(pid) {
  clearTimeout(saveTimer)
  const patch = { ...dirty }
  const keys = Object.keys(patch)
  if (!keys.length || !pid) {
    saveState.value = 'idle'
    return
  }
  for (const k of keys) delete dirty[k]
  try {
    await store.updateProject(pid, patch)
    if (pid === currentPid.value) {
      saveState.value = 'saved'
      setTimeout(() => {
        if (saveState.value === 'saved') saveState.value = 'idle'
      }, 1500)
    }
  } catch (e) {
    ui.error(e.message)
    if (pid === currentPid.value) {
      hydrateInputs(store.projects.find((x) => x.id === pid) || null)
      saveState.value = 'idle'
    }
  }
}

onBeforeUnmount(() => flushSave(currentPid.value))

function selectProject(id) {
  selectedId.value = id
}

function projectColor(p) {
  return DOMAIN_COLORS[p?.domain] || '#64748b'
}

// Selector cards + the comparison chart both need every project's summarized numbers.
const summaries = computed(() => store.projects.map((p) => ({ project: p, ...summarize(p) })))

const compareRows = computed(() =>
  summaries.value.map((s) => ({
    name: s.project.name,
    performance: s.results.performanceRating,
    roi: s.results.roiScore,
    health: s.results.healthScore,
  })),
)
</script>

<template>
  <div class="view summaries-view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Summaries</div>
        <h1 class="page-title">Project pipeline</h1>
        <p class="page-subtitle">Inputs → calculations → final results</p>
      </div>
      <span class="updated">{{ store.projects.length }} Projects</span>
    </header>

    <div v-if="!store.projects.length" class="empty-state card">
      No projects yet — create one to see its pipeline here.
    </div>

    <template v-else>
      <!-- Flow indicator -->
      <div class="flow-strip">
        <template v-for="(step, i) in flowSteps" :key="step.step">
          <div class="flow-chip lc-chip">
            <span class="flow-num">{{ step.step }}</span>
            <AppIcon :name="step.icon" :size="13" />
            <span>{{ step.label }}</span>
          </div>
          <span v-if="i < flowSteps.length - 1" class="flow-arrow">→</span>
        </template>
      </div>

      <!-- Project selector cards -->
      <div class="selector-grid">
        <button
          v-for="s in summaries"
          :key="s.project.id"
          type="button"
          class="selector-card lc-surface lc-lift"
          :class="{ active: s.project.id === selectedProject?.id }"
          :style="
            s.project.id === selectedProject?.id
              ? { borderColor: projectColor(s.project), backgroundColor: `${projectColor(s.project)}0d` }
              : {}
          "
          @click="selectProject(s.project.id)"
        >
          <span class="selector-icon" :style="{ background: `${projectColor(s.project)}22`, color: projectColor(s.project) }">
            <AppIcon name="target" :size="13" />
          </span>
          <span class="selector-text">
            <span class="selector-name">{{ s.project.name }}</span>
            <span class="selector-domain">{{ s.project.domain || '—' }}</span>
          </span>
        </button>
      </div>

      <!-- Active project pipeline -->
      <div v-if="selectedProject" class="pipeline-grid">
        <!-- Step 1: Project -->
        <div class="card step-card" :style="{ borderColor: `${projectColor(selectedProject)}40` }">
          <div class="step-head">
            <span class="step-num">1</span>
            <h4>Project</h4>
          </div>
          <div class="step-body step1-body">
            <span class="proj-icon" :style="{ background: `${projectColor(selectedProject)}22`, color: projectColor(selectedProject) }">
              <AppIcon name="target" :size="18" />
            </span>
            <div>
              <h3 class="proj-name">{{ selectedProject.name }}</h3>
              <span class="domain-badge">{{ selectedProject.domain || '—' }}</span>
            </div>
            <div class="proj-id">
              <p class="label-sm">ID</p>
              <p class="mono id-value">P{{ selectedProject.id }}</p>
            </div>
          </div>
        </div>

        <!-- Step 2: Inputs -->
        <div class="card step-card">
          <div class="step-head">
            <span class="step-num">2</span>
            <div>
              <h4>Inputs</h4>
              <p class="step-sub">
                <span v-if="saveState === 'saving'">Saving…</span>
                <span v-else-if="saveState === 'saved'" class="saved">Saved ✓</span>
                <span v-else>Edit values to recalculate</span>
              </p>
            </div>
          </div>
          <div class="step-body input-list">
            <label class="input-field">
              <span>Budget (฿)</span>
              <input
                type="number" min="0" class="input"
                :value="inputs.budget"
                @input="setInput('budget', $event.target.valueAsNumber)"
              />
            </label>
            <label class="input-field">
              <span>Team Size</span>
              <input
                type="number" min="1" class="input"
                :value="inputs.teamSize"
                @input="setInput('teamSize', $event.target.valueAsNumber)"
              />
            </label>
            <label class="input-field">
              <span>Duration (weeks)</span>
              <div class="duration-row">
                <input type="number" min="1" class="input" v-model.number="inputs.durationWeeks" />
                <button type="button" class="icon-btn" title="Reset to project dates" @click="resetDuration">↺</button>
              </div>
              <small class="field-hint">Derived from start/due date — not saved</small>
            </label>
            <label class="input-field">
              <span>Complexity (1–10)</span>
              <input
                type="number" min="1" max="10" class="input"
                :value="inputs.complexity"
                @input="setInput('complexity', $event.target.valueAsNumber)"
              />
            </label>
          </div>
        </div>

        <!-- Step 3: Calculations -->
        <div class="card step-card">
          <div class="step-head">
            <span class="step-num">3</span>
            <div>
              <h4>Calculations</h4>
              <p class="step-sub">Derived from inputs</p>
            </div>
          </div>
          <div class="step-body">
            <MetricRow label="Cost / Resource" :value="baht(metrics.costPerResource)" formula="budget ÷ teamSize" />
            <MetricRow label="Weekly Burn Rate" :value="baht(metrics.weeklyBurnRate)" formula="budget ÷ duration" />
            <MetricRow
              label="Productivity Index"
              :value="metrics.productivityIndex.toFixed(1)"
              formula="(team × 10) ÷ complexity"
              highlight
            />
            <MetricRow
              label="Resource Efficiency"
              :value="metrics.resourceEfficiency.toFixed(2)"
              formula="budget ÷ (team × weeks × 100)"
              highlight
            />
          </div>
        </div>

        <!-- Step 4: Final Results -->
        <div class="card step-card">
          <div class="step-head">
            <span class="step-num">4</span>
            <div>
              <h4>Final Results</h4>
              <p class="step-sub">Calculated from Step 3</p>
            </div>
          </div>
          <div class="step-body">
            <div class="final-top">
              <div>
                <p class="label-sm">Efficiency Grade</p>
                <GradeChip :grade="grade" />
              </div>
              <div class="final-cost">
                <p class="label-sm">Total Cost</p>
                <p class="cost-value mono readout">{{ baht(results.totalCost) }}</p>
              </div>
            </div>
            <div class="ring-grid">
              <RingGauge :value="results.roiScore" :color="SUMMARY_COLORS.roi" label="ROI Score" />
              <RingGauge :value="results.healthScore" :color="SUMMARY_COLORS.health" label="Health" />
              <RingGauge :value="results.performanceRating" :color="SUMMARY_COLORS.performance" label="Performance" />
              <RingGauge :value="results.safety" :color="SUMMARY_COLORS.safety" label="Safety" />
            </div>
          </div>
        </div>
      </div>

      <!-- Detail charts -->
      <div v-if="selectedProject" class="detail-grid">
        <ScoreBarChart :results="results" />
        <PerformanceRadar :results="results" :efficiency="efficiency" :color="projectColor(selectedProject)" />
      </div>

      <!-- All-projects comparison -->
      <ProjectsCompareChart :rows="compareRows" />
    </template>
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
.empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-dim);
  font-size: 13px;
}

/* Flow strip */
.flow-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-sunken);
  border-radius: 10px;
  overflow-x: auto;
  margin-bottom: 16px;
}
/* Surface (glass pill) from the shared .lc-chip helper. */
.flow-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text);
}
.flow-num {
  width: 16px; height: 16px; border-radius: 50%;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
  font-size: 10px; font-weight: 700;
  display: grid; place-items: center;
}
.flow-arrow { color: var(--text-dim); flex-shrink: 0; }

/* Selector grid */
.selector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}
/* Surface (frost/rim/lift) from the shared .lc-surface / .lc-lift helpers;
   the active state's border + tint come from inline styles in the template.
   Compact pill: icon + name/domain in a single row, no grade/percent foot. */
.selector-card {
  display: flex;
  align-items: center;
  gap: 9px;
  text-align: left;
  padding: 9px 11px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition:
    transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.22s ease,
    border-color 0.22s ease;
}
.selector-icon {
  width: 26px; height: 26px; border-radius: 8px;
  display: grid; place-items: center;
  flex-shrink: 0;
  transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.selector-text { min-width: 0; display: flex; flex-direction: column; }
.selector-name {
  font-size: 12.5px; font-weight: 600; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.25;
  transition: letter-spacing 0.22s ease;
}
.selector-domain {
  font-size: 10.5px; color: var(--text-dim); margin-top: 1px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* Hover microinteraction: lift + spring the icon, nudge the label. */
.selector-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 22px -12px rgba(0, 0, 0, 0.55);
}
.selector-card:hover .selector-icon {
  transform: scale(1.14) rotate(-6deg);
}
.selector-card:hover .selector-name { letter-spacing: 0.2px; }
@media (prefers-reduced-motion: reduce) {
  .selector-card,
  .selector-icon,
  .selector-name { transition: none; }
  .selector-card:hover { transform: none; }
  .selector-card:hover .selector-icon { transform: none; }
}

/* Pipeline row */
.pipeline-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.step-card { border: 2px solid var(--border); }
.step-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px 8px;
}
.step-head h4 { font-size: 13px; font-weight: 700; color: var(--text); margin: 0; }
.step-sub { font-size: 11px; color: var(--text-dim); margin-top: 1px; }
.step-sub .saved { color: var(--success); }
.step-num {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent); color: #fff;
  font-size: 11px; font-weight: 700;
  display: grid; place-items: center;
}
.step-body { padding: 8px 16px 16px; }

.step1-body { display: flex; flex-direction: column; gap: 10px; }
.proj-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: grid; place-items: center; flex-shrink: 0;
}
.proj-name { font-size: 14px; font-weight: 700; color: var(--text); line-height: 1.25; }
.domain-badge {
  display: inline-block; margin-top: 4px;
  font-size: 10.5px; font-weight: 700; color: var(--text-dim);
  background: var(--bg-sunken); border-radius: 6px; padding: 2px 7px;
}
.proj-id { padding-top: 8px; border-top: 1px solid var(--border); }
.label-sm { font-size: 10.5px; color: var(--text-dim); margin-bottom: 2px; }
.id-value { font-size: 11px; color: var(--text-dim); }

.input-list { display: flex; flex-direction: column; gap: 10px; }
.input-field { display: block; }
.input-field > span { display: block; font-size: 11px; font-weight: 600; color: var(--text-dim); margin-bottom: 4px; }
.input-field .input { height: 32px; padding: 6px 9px; font-size: 12.5px; }
.duration-row { display: flex; gap: 6px; }
.duration-row .input { flex: 1; }
.duration-row .icon-btn { width: 32px; height: 32px; }
.field-hint { display: block; font-size: 10px; color: var(--text-dim); margin-top: 3px; }

.final-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px; }
.final-cost { text-align: right; }
.cost-value { font-size: 15px; font-weight: 700; color: var(--text); }
.ring-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

@media (max-width: 1100px) {
  .pipeline-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 760px) {
  .pipeline-grid { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: 1fr; }
  .selector-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 380px) {
  .ring-grid { grid-template-columns: 1fr; }
}
</style>

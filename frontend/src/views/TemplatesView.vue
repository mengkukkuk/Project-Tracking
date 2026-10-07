<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { api } from '@/api'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import AppIcon from '@/components/AppIcon.vue'
import RouteSkeleton from '@/components/RouteSkeleton.vue'

const ui = useUiStore()
const { templateLabel } = useFormat()

const templates = ref([])
const selectedNo = ref(null)
const loading = ref(true)
const detailLoading = ref(false)
const saving = ref(false)

// Edits are staged in `draft` and only sent to the server by Save. `original`
// is the last-loaded server state, used to diff on save and to detect dirtiness.
const draft = ref(null)
const original = ref(null)

let seq = 0
const newKey = () => `new-${++seq}`

const newProcess = ref({ process: '', dayRange: 1 })
const newTask = ref({}) // process key -> { task, results, undertaker }

const selected = computed(() => templates.value.find((t) => t.templateNo === selectedNo.value))

function toDraft(detail) {
  return {
    name: detail.name || '',
    processes: detail.processes.map((p) => ({
      key: `p${p.id}`,
      id: p.id,
      processId: p.processId,
      process: p.process || '',
      dayRange: p.dayRange ?? 0,
      deleted: false,
      tasks: p.tasks.map((t) => ({
        key: `t${t.id}`,
        id: t.id,
        task: t.task || '',
        results: t.results || '',
        undertaker: t.undertaker || '',
        deleted: false,
      })),
    })),
  }
}

const clone = (v) => JSON.parse(JSON.stringify(v))
const isDirty = computed(
  () => !!draft.value && JSON.stringify(draft.value) !== JSON.stringify(original.value),
)

const visibleProcesses = computed(() => (draft.value?.processes || []).filter((p) => !p.deleted))

async function loadList(keepSelection = true) {
  const { items } = await api.listTemplates()
  templates.value = items
  if (!keepSelection || !items.some((t) => t.templateNo === selectedNo.value)) {
    selectedNo.value = items[0]?.templateNo ?? null
  }
}

async function loadDetail() {
  newProcess.value = { process: '', dayRange: 1 }
  newTask.value = {}
  if (selectedNo.value == null) {
    draft.value = original.value = null
    return
  }
  detailLoading.value = true
  try {
    const detail = await api.getTemplate(selectedNo.value)
    original.value = toDraft(detail)
    draft.value = clone(original.value)
  } catch (e) {
    ui.error(e.message)
  } finally {
    detailLoading.value = false
  }
}

function confirmDiscard() {
  return !isDirty.value || window.confirm('Discard your unsaved changes?')
}

async function select(no) {
  if (no === selectedNo.value || !confirmDiscard()) return
  selectedNo.value = no
  await loadDetail()
}

async function createTemplate(cloneFrom) {
  if (!confirmDiscard()) return
  saving.value = true
  try {
    const { templateNo } = await api.createTemplate(cloneFrom ? { cloneFrom } : {})
    await loadList()
    selectedNo.value = templateNo
    await loadDetail()
    ui.success(`Template ${templateNo} created — give it a name and save`)
  } catch (e) {
    ui.error(e.message)
  } finally {
    saving.value = false
  }
}

// ── Staged edits ───────────────────────────────────────────────────────────

function addProcess() {
  const name = newProcess.value.process.trim()
  if (!name) return
  draft.value.processes.push({
    key: newKey(),
    id: null,
    processId: null,
    process: name,
    dayRange: Number(newProcess.value.dayRange) || 0,
    deleted: false,
    tasks: [],
  })
  newProcess.value = { process: '', dayRange: 1 }
}

function removeProcess(proc) {
  if (visibleProcesses.value.length <= 1) return
  if (proc.id) proc.deleted = true
  else draft.value.processes = draft.value.processes.filter((p) => p !== proc)
}

function taskDraft(proc) {
  if (!newTask.value[proc.key]) newTask.value[proc.key] = { task: '', results: '', undertaker: '' }
  return newTask.value[proc.key]
}

function addTask(proc) {
  const d = taskDraft(proc)
  if (!d.task.trim()) return
  proc.tasks.push({ key: newKey(), id: null, ...d, task: d.task.trim(), deleted: false })
  newTask.value[proc.key] = { task: '', results: '', undertaker: '' }
}

function removeTask(proc, task) {
  if (task.id) task.deleted = true
  else proc.tasks = proc.tasks.filter((t) => t !== task)
}

// ── Save ───────────────────────────────────────────────────────────────────

function validate() {
  for (const p of visibleProcesses.value) {
    if (!p.process.trim()) return 'Every process needs a name'
    const d = Number(p.dayRange)
    if (!Number.isInteger(d) || d < 0) return `"${p.process}": days must be a whole number ≥ 0`
    if (p.tasks.some((t) => !t.deleted && !t.task.trim())) return `"${p.process}": a task is empty`
  }
  return null
}

async function save() {
  const problem = validate()
  if (problem) return ui.error(problem)
  const no = selectedNo.value
  const origProc = new Map(original.value.processes.map((p) => [p.id, p]))
  const origTask = new Map(
    original.value.processes.flatMap((p) => p.tasks).map((t) => [t.id, t]),
  )
  saving.value = true
  try {
    const name = draft.value.name.trim()
    if (name !== original.value.name) await api.renameTemplate(no, name)

    // 1) New processes first (so replacing every process never hits the
    //    "keep at least one process" guard), each with its tasks.
    for (const p of draft.value.processes) {
      if (p.id || p.deleted) continue
      const made = await api.createTemplateProcess(no, {
        process: p.process.trim(),
        dayRange: Number(p.dayRange),
      })
      for (const t of p.tasks.filter((t) => !t.deleted)) {
        await api.createTemplateTask({
          templateNo: no,
          processId: made.processId,
          task: t.task.trim(),
          results: t.results,
          undertaker: t.undertaker,
        })
      }
    }

    // 2) Existing, surviving processes: rename / day budget, then their tasks.
    for (const p of draft.value.processes) {
      if (!p.id || p.deleted) continue
      const o = origProc.get(p.id)
      const patch = {}
      if (p.process.trim() !== o.process) patch.process = p.process.trim()
      if (Number(p.dayRange) !== o.dayRange) patch.dayRange = Number(p.dayRange)
      if (Object.keys(patch).length) await api.updateProcessTag(p.id, patch)

      for (const t of p.tasks) {
        if (!t.id) {
          if (t.deleted) continue
          await api.createTemplateTask({
            templateNo: no,
            processId: p.processId,
            task: t.task.trim(),
            results: t.results,
            undertaker: t.undertaker,
          })
        } else if (t.deleted) {
          await api.deleteTemplateTask(t.id)
        } else {
          const ot = origTask.get(t.id)
          const tp = {}
          for (const f of ['task', 'results', 'undertaker']) {
            if (t[f].trim() !== ot[f]) tp[f] = t[f].trim()
          }
          if (Object.keys(tp).length) await api.updateTemplateTask(t.id, tp)
        }
      }
    }

    // 3) Deleted processes last (the server also drops their tasks).
    for (const p of draft.value.processes) {
      if (p.id && p.deleted) await api.deleteProcessTag(p.id)
    }

    await Promise.all([loadList(), loadDetail()])
    ui.success('Template saved')
  } catch (e) {
    ui.error(e.message)
    // Show what actually persisted; part of the batch may have been applied.
    await Promise.all([loadList(), loadDetail()])
  } finally {
    saving.value = false
  }
}

function discard() {
  draft.value = clone(original.value)
  newProcess.value = { process: '', dayRange: 1 }
  newTask.value = {}
}

// Guard against losing staged edits on navigation / tab close.
onBeforeRouteLeave(() => confirmDiscard())
function warnUnload(e) {
  if (isDirty.value) e.preventDefault()
}
window.addEventListener('beforeunload', warnUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnUnload))

onMounted(async () => {
  try {
    await loadList(false)
    await loadDetail()
  } catch (e) {
    ui.error(e.message)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <RouteSkeleton v-if="loading" variant="generic" />

  <div v-else class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Process checklist</div>
        <h1 class="page-title">Templates</h1>
        <p class="page-subtitle">
          Each template is a set of processes and tasks. A project picks one when it is created
          (and can switch later); editing a template never changes existing projects.
        </p>
      </div>
    </header>

    <div class="layout">
      <!-- Template list -->
      <aside class="list card">
        <button
          v-for="t in templates"
          :key="t.templateNo"
          class="t-item"
          :class="{ active: t.templateNo === selectedNo }"
          @click="select(t.templateNo)"
        >
          <span class="t-name">{{ t.name || `Template ${t.templateNo}` }}</span>
          <span class="t-meta mono">
            #{{ t.templateNo }} · {{ t.processCount }} processes · {{ t.taskCount }} tasks
            <template v-if="t.projectCount"> · {{ t.projectCount }} projects</template>
          </span>
        </button>
        <div class="t-actions">
          <button class="btn sm" :disabled="saving" @click="createTemplate()">
            <AppIcon name="plus" :size="14" /> New template
          </button>
          <button
            v-if="selected"
            class="btn ghost sm"
            :disabled="saving"
            @click="createTemplate(selected.templateNo)"
          >
            <AppIcon name="copy" :size="14" /> Clone #{{ selected.templateNo }}
          </button>
        </div>
      </aside>

      <!-- Editor -->
      <section class="editor">
        <div v-if="detailLoading && !draft" class="state">Loading template…</div>
        <div v-else-if="!draft" class="state">No templates yet — create one.</div>

        <template v-else>
          <div class="savebar card" :class="{ dirty: isDirty }">
            <label class="name-field">
              <span>Template name</span>
              <input
                v-model="draft.name"
                class="input"
                maxlength="100"
                :placeholder="templateLabel(selectedNo)"
                :disabled="saving"
              />
            </label>
            <span class="state-note" :class="{ on: isDirty }">
              {{ isDirty ? 'Unsaved changes' : 'All changes saved' }}
            </span>
            <button class="btn ghost sm" :disabled="saving || !isDirty" @click="discard">
              Discard
            </button>
            <button class="btn sm" :disabled="saving || !isDirty" @click="save">
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
          </div>

          <article v-for="proc in visibleProcesses" :key="proc.key" class="proc card">
            <header class="proc-head">
              <span class="proc-no mono">{{ proc.processId ?? '+' }}</span>
              <input
                v-model="proc.process"
                class="input proc-name"
                :disabled="saving"
                aria-label="Process name"
              />
              <label class="days">
                <input
                  v-model="proc.dayRange"
                  class="input mono"
                  type="number"
                  min="0"
                  :disabled="saving"
                  aria-label="Days"
                />
                <span>days</span>
              </label>
              <button
                class="icon-btn"
                :disabled="saving || visibleProcesses.length <= 1"
                :title="
                  visibleProcesses.length <= 1
                    ? 'A template must keep at least one process'
                    : 'Delete process'
                "
                aria-label="Delete process"
                @click="removeProcess(proc)"
              >
                <AppIcon name="trash" :size="14" />
              </button>
            </header>

            <div class="tasks">
              <div class="task-row head">
                <span>Task</span><span>Result</span><span>Owner</span><span />
              </div>
              <div
                v-for="task in proc.tasks.filter((t) => !t.deleted)"
                :key="task.key"
                class="task-row"
              >
                <input v-model="task.task" class="input" :disabled="saving" aria-label="Task" />
                <input v-model="task.results" class="input" :disabled="saving" aria-label="Result" />
                <input
                  v-model="task.undertaker"
                  class="input"
                  :disabled="saving"
                  aria-label="Owner"
                />
                <button
                  class="icon-btn"
                  :disabled="saving"
                  title="Delete task"
                  aria-label="Delete task"
                  @click="removeTask(proc, task)"
                >
                  <AppIcon name="close" :size="14" />
                </button>
              </div>

              <form class="task-row add" @submit.prevent="addTask(proc)">
                <input v-model="taskDraft(proc).task" class="input" placeholder="New task…" />
                <input v-model="taskDraft(proc).results" class="input" placeholder="Result" />
                <input v-model="taskDraft(proc).undertaker" class="input" placeholder="Owner" />
                <button
                  class="btn ghost sm"
                  type="submit"
                  :disabled="saving || !taskDraft(proc).task.trim()"
                >
                  Add
                </button>
              </form>
            </div>
          </article>

          <form class="proc card add-proc" @submit.prevent="addProcess">
            <input
              v-model="newProcess.process"
              class="input proc-name"
              placeholder="New process name…"
            />
            <label class="days">
              <input v-model="newProcess.dayRange" class="input mono" type="number" min="0" />
              <span>days</span>
            </label>
            <button
              class="btn ghost sm"
              type="submit"
              :disabled="saving || !newProcess.process.trim()"
            >
              <AppIcon name="plus" :size="14" /> Add process
            </button>
          </form>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 20px;
  align-items: start;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.state { padding: 48px; text-align: center; color: var(--text-dim); }

.list { padding: 8px; display: grid; gap: 4px; position: sticky; top: 16px; }
.t-item {
  display: grid; gap: 2px; text-align: left; width: 100%;
  padding: 10px 12px; border: 1px solid transparent; border-radius: 8px;
  background: transparent; color: var(--text); font: inherit; cursor: pointer;
  transition: background-color .12s, border-color .12s;
}
.t-item:hover { background: var(--bg-sunken); }
.t-item.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
.t-name { font-weight: 700; font-size: 13px; }
.t-meta { font-size: 11px; color: var(--text-dim); }
.t-actions { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 4px 2px; border-top: 1px solid var(--border); margin-top: 4px; }

.editor { display: grid; gap: 14px; min-width: 0; }

.savebar {
  position: sticky; top: 8px; z-index: 5;
  display: flex; align-items: flex-end; gap: 12px; padding: 12px 16px;
  transition: border-color .15s, box-shadow .15s;
}
.savebar.dirty {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 16%, transparent);
}
.name-field { flex: 1; min-width: 0; display: grid; gap: 4px; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--text-dim); }
.name-field .input { text-transform: none; letter-spacing: 0; font-size: 14px; font-weight: 700; color: var(--text); }
.state-note { font-size: 12px; color: var(--text-dim); white-space: nowrap; padding-bottom: 9px; }
.state-note.on { color: var(--warning); font-weight: 700; }

.proc { padding: 14px 16px; }
.proc-head, .add-proc { display: flex; align-items: center; gap: 10px; }
.proc-no {
  display: inline-grid; place-items: center; min-width: 26px; height: 26px; border-radius: 7px;
  font-size: 12px; font-weight: 700; color: var(--accent);
  background: color-mix(in srgb, var(--accent) 14%, transparent);
}
.proc-name { flex: 1; min-width: 0; font-weight: 700; }
.days { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-dim); }
.days .input { width: 64px; text-align: right; }

.tasks { display: grid; gap: 6px; margin-top: 12px; }
.task-row {
  display: grid; grid-template-columns: 2.4fr 1.6fr 1fr 34px; gap: 8px; align-items: center;
}
.task-row.head {
  font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--text-dim); padding: 0 2px;
}
.task-row.add { margin-top: 4px; grid-template-columns: 2.4fr 1.6fr 1fr 64px; }

@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .list { position: static; }
  .savebar { flex-wrap: wrap; }
  .task-row, .task-row.add { grid-template-columns: 1fr 34px; }
  .task-row.head { display: none; }
  .task-row > :nth-child(2), .task-row > :nth-child(3) { grid-column: 1; }
}
</style>

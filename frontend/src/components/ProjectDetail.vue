<script setup>
import { ref } from 'vue'
import { useProjectsStore, STAGES, taskProgress } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import StatusBadge from './StatusBadge.vue'
import PriorityBadge from './PriorityBadge.vue'
import ProgressBar from './ProgressBar.vue'
import AppIcon from './AppIcon.vue'

const emit = defineEmits(['close', 'edit'])
const store = useProjectsStore()
const ui = useUiStore()
const { baht, date, relative, daysUntil } = useFormat()

const newTask = ref('')
const newComment = ref('')
const busy = ref(false)
const tab = ref('summary')

const tabs = [
  ['summary', 'Summary', 'overview'],
  ['tasks', 'Tasks', 'check'],
  ['comments', 'Comments', 'comment'],
  ['activity', 'Activity', 'activity'],
]

async function addTask() {
  const title = newTask.value.trim()
  if (!title || !store.current) return
  busy.value = true
  try {
    await store.addTask(store.current.id, { title })
    newTask.value = ''
  } catch (e) { ui.error(e.message) } finally { busy.value = false }
}

async function toggleTask(t) {
  try { await store.toggleTask(t) } catch (e) { ui.error(e.message) }
}
async function removeTask(t) {
  try { await store.deleteTask(t) } catch (e) { ui.error(e.message) }
}

async function addComment() {
  const body = newComment.value.trim()
  if (!body || !store.current) return
  busy.value = true
  try {
    await store.addComment(store.current.id, body)
    newComment.value = ''
  } catch (e) { ui.error(e.message) } finally { busy.value = false }
}
async function removeComment(c) {
  try { await store.deleteComment(store.current.id, c.id) } catch (e) { ui.error(e.message) }
}

async function quickUpdate(patch) {
  if (!store.current) return
  try {
    await store.updateProject(store.current.id, patch)
    ui.success('Project updated')
  } catch (e) {
    ui.error(e.message)
  }
}

async function remove() {
  if (!store.current) return
  if (!confirm(`Delete project "${store.current.name}"?`)) return
  try {
    await store.deleteProject(store.current.id)
    emit('close')
  } catch (e) { ui.error(e.message) }
}

function dueClass(iso) {
  const d = daysUntil(iso)
  if (d == null) return ''
  if (d < 0) return 'overdue'
  if (d <= 7) return 'soon'
  return ''
}
</script>

<template>
  <Teleport to="body">
    <div class="drawer-overlay" @click.self="emit('close')">
      <aside class="drawer" aria-label="Project details">
        <header class="drawer-head">
          <div class="title-wrap">
            <span class="eyebrow">Project detail</span>
            <h2>{{ store.current?.name || 'Loading project...' }}</h2>
          </div>
          <button class="icon-btn" type="button" aria-label="Close" @click="emit('close')">
            <AppIcon name="close" :size="16" />
          </button>
        </header>

        <div v-if="store.detailLoading" class="loading">Loading project details...</div>

        <template v-else-if="store.current">
          <section class="hero">
            <div class="badges">
              <StatusBadge :status="store.current.status" />
              <PriorityBadge :priority="store.current.priority" />
              <span class="value mono">{{ baht(store.current.value) }}</span>
            </div>
            <div class="head-actions">
              <button class="btn ghost sm" @click="emit('edit', store.current)">
                <AppIcon name="edit" :size="14" />
                Edit
              </button>
              <button class="btn danger sm" @click="remove">
                <AppIcon name="trash" :size="14" />
                Delete
              </button>
            </div>
          </section>

          <section class="quick card">
            <label>
              <span>Status</span>
              <select :value="store.current.status" @change="quickUpdate({ status: $event.target.value })">
                <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
              </select>
            </label>
            <label>
              <span>Progress (from tasks)</span>
              <ProgressBar :value="taskProgress(store.current)" :height="8" />
            </label>
            <strong class="progress-value mono">{{ taskProgress(store.current) }}%</strong>
          </section>

          <nav class="tabs" aria-label="Project detail sections">
            <button
              v-for="[id, label, icon] in tabs"
              :key="id"
              type="button"
              :class="{ active: tab === id }"
              @click="tab = id"
            >
              <AppIcon :name="icon" :size="14" />
              {{ label }}
            </button>
          </nav>

          <div class="drawer-body">
            <section v-if="tab === 'summary'" class="panel">
              <p v-if="store.current.description" class="desc">{{ store.current.description }}</p>

              <div class="meta">
                <div><span>Domain</span>{{ store.current.domain || '-' }}</div>
                <div><span>Customer</span>{{ store.current.customer || '-' }}</div>
                <div><span>PM</span>{{ store.current.pm || '-' }}</div>
                <div><span>Fiscal year</span>{{ store.current.fiscalYear }}</div>
                <div><span>Start date</span>{{ date(store.current.startDate) }}</div>
                <div :class="dueClass(store.current.dueDate)"><span>Due date</span>{{ date(store.current.dueDate) }}</div>
              </div>

              <div class="prog">
                <span class="sec-label">Progress</span>
                <ProgressBar :value="taskProgress(store.current)" :height="8" show-label />
              </div>

              <div v-if="store.current.tags?.length" class="tags">
                <span v-for="t in store.current.tags" :key="t.id" class="tag" :style="{ background: t.color + '22', color: t.color }">
                  {{ t.name }}
                </span>
              </div>
            </section>

            <section v-if="tab === 'tasks'" class="panel">
              <h3 class="sec-title">Checklist <span>{{ store.current.taskDone }}/{{ store.current.taskCount }}</span></h3>
              <ul class="tasks">
                <li v-for="t in store.current.tasks" :key="t.id">
                  <label>
                    <input type="checkbox" :checked="t.done" @change="toggleTask(t)" />
                    <span :class="{ done: t.done }">{{ t.title }}</span>
                  </label>
                  <span v-if="t.assignee" class="assignee">{{ t.assignee }}</span>
                  <button class="del" @click="removeTask(t)">
                    <AppIcon name="close" :size="13" />
                  </button>
                </li>
                <li v-if="!store.current.tasks.length" class="empty">No tasks yet.</li>
              </ul>
              <form class="add" @submit.prevent="addTask">
                <input v-model="newTask" class="input" placeholder="Add a task..." />
                <button class="btn sm" :disabled="busy">Add</button>
              </form>
            </section>

            <section v-if="tab === 'comments'" class="panel">
              <form class="add comment-add" @submit.prevent="addComment">
                <input v-model="newComment" class="input" placeholder="Write a comment..." />
                <button class="btn sm" :disabled="busy">Send</button>
              </form>
              <ul class="comments">
                <li v-for="c in store.current.comments" :key="c.id">
                  <div class="c-head">
                    <strong>{{ c.user?.name || 'Unknown' }}</strong>
                    <span class="time">{{ relative(c.createdAt) }}</span>
                    <button class="del" @click="removeComment(c)">
                      <AppIcon name="close" :size="13" />
                    </button>
                  </div>
                  <div class="c-body">{{ c.body }}</div>
                </li>
                <li v-if="!store.current.comments.length" class="empty">No comments yet.</li>
              </ul>
            </section>

            <section v-if="tab === 'activity'" class="panel">
              <ul class="activity">
                <li v-for="a in store.current.activities" :key="a.id">
                  <span class="dot" />
                  <div>
                    <span class="act">{{ a.detail }}</span>
                    <span class="time">{{ a.user?.name || 'System' }} · {{ relative(a.createdAt) }}</span>
                  </div>
                </li>
                <li v-if="!store.current.activities.length" class="empty">No activity yet.</li>
              </ul>
            </section>
          </div>
        </template>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  justify-content: flex-end;
  background: rgba(15, 23, 42, .42);
  backdrop-filter: blur(2px);
  animation: fade-in .16s ease;
}
@keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
.drawer {
  width: min(760px, 100vw);
  height: 100vh;
  background: var(--surface);
  border-left: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  animation: slide-in .2s ease;
}
@keyframes slide-in { from { transform: translateX(24px); opacity: .8; } to { transform: none; opacity: 1; } }
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.eyebrow {
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.drawer-head h2 {
  margin: 3px 0 0;
  color: var(--text);
  font-size: 18px;
  line-height: 1.25;
}
.loading {
  padding: 48px 20px;
  color: var(--text-dim);
  text-align: center;
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 16px 20px 0;
}
.badges,
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.value { font-size: 15px; font-weight: 800; }
.quick {
  display: grid;
  grid-template-columns: minmax(150px, 190px) 1fr auto;
  align-items: end;
  gap: 12px;
  margin: 14px 20px 0;
  padding: 12px;
}
.quick label {
  display: grid;
  gap: 5px;
}
.quick span {
  color: var(--text-dim);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .05em;
  text-transform: uppercase;
}
.quick select {
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  padding: 0 10px;
  font: inherit;
  font-size: 12px;
}
.quick input[type=range] {
  accent-color: var(--accent);
}
.progress-value {
  color: var(--text);
  font-size: 18px;
}
.tabs {
  display: flex;
  gap: 6px;
  padding: 14px 20px 0;
  border-bottom: 1px solid var(--border);
}
.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-dim);
  padding: 10px 8px;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.drawer-body {
  overflow-y: auto;
  padding: 18px 20px 24px;
}
.panel {
  display: grid;
  gap: 16px;
}
.desc { color: var(--text-dim); font-size: 13px; line-height: 1.6; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.meta > div { font-size: 13px; color: var(--text); padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-sunken); }
.meta span { display: block; font-size: 10px; color: var(--text-dim); margin-bottom: 3px; text-transform: uppercase; font-weight: 800; }
.meta .overdue { color: var(--danger); }
.meta .soon { color: var(--warning); }
.prog { display: grid; gap: 8px; }
.sec-label,
.sec-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.sec-title {
  display: flex;
  justify-content: space-between;
}
.sec-title span { color: var(--text-dim); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 5px; }
.tasks, .comments, .activity { list-style: none; display: grid; gap: 8px; }
.tasks li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tasks label { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
.tasks input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); }
.tasks .done { text-decoration: line-through; color: var(--text-dim); }
.assignee { font-size: 10px; color: var(--text-dim); background: var(--bg-sunken); padding: 1px 6px; border-radius: 4px; }
.del { display: grid; place-items: center; background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 3px; opacity: .55; }
.del:hover { opacity: 1; color: var(--danger); }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; }
.add { display: flex; gap: 8px; }
.comment-add { order: -1; }
.comments li { background: var(--bg-sunken); border-radius: 8px; padding: 10px; border: 1px solid var(--border); }
.c-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.c-head strong { color: var(--text); }
.time { color: var(--text-dim); font-size: 11px; }
.c-head .del { margin-left: auto; }
.c-body { font-size: 13px; color: var(--text); margin-top: 4px; line-height: 1.5; }
.activity li { display: flex; gap: 10px; font-size: 12px; }
.activity .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-top: 5px; flex-shrink: 0; }
.activity .act { display: block; color: var(--text); }
.activity .time { display: block; margin-top: 2px; }

@media (max-width: 680px) {
  .drawer { width: 100vw; }
  .quick { grid-template-columns: 1fr; }
  .tabs { overflow-x: auto; }
  .meta { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 460px) {
  .meta { grid-template-columns: 1fr; }
  .add { flex-direction: column; }
}
</style>

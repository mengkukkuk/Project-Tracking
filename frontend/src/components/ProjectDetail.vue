<script setup>
import { ref } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useFormat } from '@/composables/useFormat'
import Modal from './Modal.vue'
import StatusBadge from './StatusBadge.vue'
import PriorityBadge from './PriorityBadge.vue'
import ProgressBar from './ProgressBar.vue'

const emit = defineEmits(['close', 'edit'])
const store = useProjectsStore()
const ui = useUiStore()
const { baht, date, relative, daysUntil } = useFormat()

const newTask = ref('')
const newComment = ref('')
const busy = ref(false)

async function addTask() {
  const title = newTask.value.trim()
  if (!title) return
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
  if (!body) return
  busy.value = true
  try {
    await store.addComment(store.current.id, body)
    newComment.value = ''
  } catch (e) { ui.error(e.message) } finally { busy.value = false }
}
async function removeComment(c) {
  try { await store.deleteComment(store.current.id, c.id) } catch (e) { ui.error(e.message) }
}

async function remove() {
  if (!confirm(`ลบโครงการ “${store.current.name}” ?`)) return
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
  <Modal :title="store.current?.name || 'รายละเอียด'" wide @close="emit('close')">
    <div v-if="store.detailLoading" class="loading">กำลังโหลด...</div>
    <div v-else-if="store.current" class="detail">
      <!-- summary -->
      <div class="summary">
        <div class="badges">
          <StatusBadge :status="store.current.status" />
          <PriorityBadge :priority="store.current.priority" />
          <span class="val mono">{{ baht(store.current.value) }}</span>
        </div>
        <div class="head-actions">
          <button class="btn ghost sm" @click="emit('edit', store.current)">✎ แก้ไข</button>
          <button class="btn danger sm" @click="remove">🗑 ลบ</button>
        </div>
      </div>

      <p v-if="store.current.description" class="desc">{{ store.current.description }}</p>

      <div class="meta">
        <div><span>กลุ่มงาน</span>{{ store.current.domain || '—' }}</div>
        <div><span>ลูกค้า</span>{{ store.current.customer || '—' }}</div>
        <div><span>PM</span>{{ store.current.pm || '—' }}</div>
        <div><span>ปีงบ</span>{{ store.current.fiscalYear }}</div>
        <div><span>วันเริ่ม</span>{{ date(store.current.startDate) }}</div>
        <div :class="dueClass(store.current.dueDate)"><span>กำหนดส่ง</span>{{ date(store.current.dueDate) }}</div>
      </div>

      <div class="prog">
        <span class="sec-label">ความคืบหน้า</span>
        <ProgressBar :value="store.current.progress" :height="8" show-label />
      </div>

      <div v-if="store.current.tags?.length" class="tags">
        <span v-for="t in store.current.tags" :key="t.id" class="tag" :style="{ background: t.color + '22', color: t.color }">
          {{ t.name }}
        </span>
      </div>

      <div class="cols">
        <!-- tasks -->
        <section class="col">
          <h4 class="sec-label">
            เช็คลิสต์งาน
            <span class="count">{{ store.current.taskDone }}/{{ store.current.taskCount }}</span>
          </h4>
          <ul class="tasks">
            <li v-for="t in store.current.tasks" :key="t.id">
              <label>
                <input type="checkbox" :checked="t.done" @change="toggleTask(t)" />
                <span :class="{ done: t.done }">{{ t.title }}</span>
              </label>
              <span v-if="t.assignee" class="assignee">{{ t.assignee }}</span>
              <button class="del" @click="removeTask(t)">✕</button>
            </li>
            <li v-if="!store.current.tasks.length" class="empty">ยังไม่มีงาน</li>
          </ul>
          <form class="add" @submit.prevent="addTask">
            <input v-model="newTask" class="input" placeholder="เพิ่มงาน..." />
            <button class="btn sm" :disabled="busy">เพิ่ม</button>
          </form>
        </section>

        <!-- comments + activity -->
        <section class="col">
          <h4 class="sec-label">ความคิดเห็น</h4>
          <form class="add" @submit.prevent="addComment">
            <input v-model="newComment" class="input" placeholder="เขียนความคิดเห็น..." />
            <button class="btn sm" :disabled="busy">ส่ง</button>
          </form>
          <ul class="comments">
            <li v-for="c in store.current.comments" :key="c.id">
              <div class="c-head">
                <strong>{{ c.user?.name || 'ไม่ทราบ' }}</strong>
                <span class="time">{{ relative(c.createdAt) }}</span>
                <button class="del" @click="removeComment(c)">✕</button>
              </div>
              <div class="c-body">{{ c.body }}</div>
            </li>
            <li v-if="!store.current.comments.length" class="empty">ยังไม่มีความคิดเห็น</li>
          </ul>

          <h4 class="sec-label" style="margin-top:16px">ประวัติกิจกรรม</h4>
          <ul class="activity">
            <li v-for="a in store.current.activities" :key="a.id">
              <span class="dot" />
              <div>
                <span class="act">{{ a.detail }}</span>
                <span class="time">{{ a.user?.name || 'ระบบ' }} · {{ relative(a.createdAt) }}</span>
              </div>
            </li>
            <li v-if="!store.current.activities.length" class="empty">—</li>
          </ul>
        </section>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.loading { padding: 40px; text-align: center; color: var(--text-dim); }
.summary { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.badges { display: flex; align-items: center; gap: 10px; }
.val { font-size: 16px; font-weight: 600; }
.head-actions { display: flex; gap: 8px; }
.desc { margin: 14px 0; color: var(--text-dim); font-size: 13px; line-height: 1.6; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }
.meta > div { font-size: 13px; color: var(--text); }
.meta span { display: block; font-size: 11px; color: var(--text-dim); margin-bottom: 2px; }
.meta .overdue { color: #ef4444; }
.meta .soon { color: #f59e0b; }
.prog { margin: 16px 0; }
.sec-label { font-size: 12px; font-weight: 700; color: var(--text); margin-bottom: 8px; display: flex; align-items: center; gap: 8px; text-transform: uppercase; letter-spacing: .04em; }
.count { font-weight: 500; color: var(--text-dim); font-size: 11px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.tag { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 5px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 8px; }
@media (max-width: 640px) { .cols { grid-template-columns: 1fr; } .meta { grid-template-columns: 1fr 1fr; } }

.tasks, .comments, .activity { list-style: none; display: flex; flex-direction: column; gap: 8px; }
.tasks li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tasks label { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
.tasks input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); }
.tasks .done { text-decoration: line-through; color: var(--text-dim); }
.assignee { font-size: 10px; color: var(--text-dim); background: var(--bg-sunken); padding: 1px 6px; border-radius: 4px; }
.del { background: none; border: none; color: var(--text-dim); cursor: pointer; font-size: 12px; opacity: .5; }
.del:hover { opacity: 1; color: var(--danger); }
.empty { color: var(--text-dim); font-size: 12px; font-style: italic; }
.add { display: flex; gap: 8px; margin-top: 10px; }

.comments li { background: var(--bg-sunken); border-radius: 8px; padding: 8px 10px; }
.c-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.c-head strong { color: var(--text); }
.time { color: var(--text-dim); font-size: 11px; }
.c-head .del { margin-left: auto; }
.c-body { font-size: 13px; color: var(--text); margin-top: 4px; line-height: 1.5; }

.activity li { display: flex; gap: 10px; font-size: 12px; }
.activity .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); margin-top: 5px; flex-shrink: 0; }
.activity .act { display: block; color: var(--text); }
.activity .time { display: block; }
</style>

<script setup>
import { reactive, ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/api'

const props = defineProps({
  project: { type: Object, default: null },
  submitting: Boolean,
})
const emit = defineEmits(['submit', 'cancel'])

const DOMAINS = ['Vision Sensor', 'Robot', 'PLC', 'IoT', 'AI']
const PRIORITIES = [
  ['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['critical', 'Critical'],
]
const FYS = ['69', '70', '71', 'future']

const p = props.project
const form = reactive({
  name: p?.name || '',
  description: p?.description || '',
  domain: p?.domain || 'IoT',
  customer: p?.customer || '',
  // status is derived from progress on the server — not user-settable.
  priority: p?.priority || 'medium',
  value: p?.value ?? 0,
  teamSize: p?.teamSize ?? '',
  complexity: p?.complexity ?? '',
  fiscalYear: p?.fiscalYear || 'future',
  startDate: p?.startDate || '',
  dueDate: p?.dueDate || '',
})

// ── Project managers (multi-select sourced from the users directory) ──
const allUsers = ref([])
const selectedPms = ref(
  // Hydrate from the project's persisted pms list when editing, else empty.
  (p?.pms || []).map((u) => ({ id: u.id, name: u.name })),
)
const pmMenuOpen = ref(false)
const pmFilter = ref('')
const pmAnchor = ref(null)

const selectedPmIds = computed(() => new Set(selectedPms.value.map((u) => u.id)))
const pmCandidates = computed(() => {
  const q = pmFilter.value.trim().toLowerCase()
  return allUsers.value
    .filter((u) => !selectedPmIds.value.has(u.id))
    .filter((u) => !q || u.name.toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q))
})

function addPm(user) {
  if (selectedPmIds.value.has(user.id)) return
  selectedPms.value.push({ id: user.id, name: user.name })
  pmFilter.value = ''
  // Keep the menu open so the user can chain-add multiple PMs quickly.
}
function removePm(user) {
  selectedPms.value = selectedPms.value.filter((u) => u.id !== user.id)
}
function togglePmMenu() {
  pmMenuOpen.value = !pmMenuOpen.value
  if (pmMenuOpen.value) pmFilter.value = ''
}
function closePmMenuOnClickOutside(e) {
  if (!pmAnchor.value) return
  if (!pmAnchor.value.contains(e.target)) pmMenuOpen.value = false
}

onMounted(async () => {
  try {
    const { items } = await api.listUsers()
    allUsers.value = items || []
  } catch (e) {
    // Silently degrade — the chip composer still shows existing selections.
    allUsers.value = []
  }
  document.addEventListener('mousedown', closePmMenuOnClickOutside)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', closePmMenuOnClickOutside)
})

const tags = ref([...(p?.tags || []).map((t) => t.name)])
const tagDraft = ref('')

function addTagFromDraft() {
  const raw = tagDraft.value.trim().replace(/,$/, '').trim()
  if (!raw) return
  if (!tags.value.includes(raw)) tags.value.push(raw)
  tagDraft.value = ''
}
function onTagKey(e) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addTagFromDraft()
  } else if (e.key === 'Backspace' && !tagDraft.value && tags.value.length) {
    tags.value.pop()
  }
}
function removeTag(t) {
  tags.value = tags.value.filter((x) => x !== t)
}

const valueDisplay = computed(() => {
  const n = Number(form.value) || 0
  return new Intl.NumberFormat('en-US').format(n)
})

const priorityLabel = computed(
  () => PRIORITIES.find(([v]) => v === form.priority)?.[1] || form.priority,
)
const fyLabel = computed(() => (form.fiscalYear === 'future' ? 'Future' : `FY${form.fiscalYear}`))

const sections = [
  { id: 'identity', num: '01', label: 'Identity' },
  { id: 'planning', num: '02', label: 'Planning' },
  { id: 'timeline', num: '03', label: 'Timeline' },
]
const active = ref('identity')

function jumpTo(id) {
  active.value = id
  const el = document.getElementById(`pf-${id}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function submit() {
  if (tagDraft.value.trim()) addTagFromDraft()
  emit('submit', {
    ...form,
    value: Number(form.value) || 0,
    teamSize: form.teamSize === '' ? null : Number(form.teamSize),
    complexity: form.complexity === '' ? null : Number(form.complexity),
    startDate: form.startDate || null,
    dueDate: form.dueDate || null,
    tags: tags.value,
    pmIds: selectedPms.value.map((u) => u.id),
  })
}
</script>

<template>
  <form class="pform" @submit.prevent="submit">
    <!-- Editorial sidebar: section index -->
    <aside class="pform-aside" aria-label="Form sections">
      <div class="aside-eyebrow">
        {{ project ? 'Editing' : 'Drafting' }}
      </div>
      <div class="aside-title">
        {{ form.name || (project ? project.name : 'Untitled project') }}
      </div>

      <ol class="aside-nav">
        <li v-for="s in sections" :key="s.id">
          <button
            type="button"
            :class="{ active: active === s.id }"
            @click="jumpTo(s.id)"
          >
            <span class="num mono">{{ s.num }}</span>
            <span class="lbl">{{ s.label }}</span>
          </button>
        </li>
      </ol>

      <div class="aside-foot">
        <span class="mono">{{ priorityLabel }} priority</span>
        <span class="aside-dot">·</span>
        <span class="mono">{{ fyLabel }}</span>
      </div>
    </aside>

    <!-- Content stream -->
    <div class="pform-stream">
      <!-- 01 Identity -->
      <section id="pf-identity" class="sec">
        <header class="sec-head">
          <span class="sec-num mono">01</span>
          <div>
            <div class="sec-eyebrow">Section one</div>
            <h3>Identity</h3>
          </div>
        </header>

        <div class="grid">
          <label class="under span2">
            <span>Project name</span>
            <input
              v-model="form.name"
              class="u-input lg"
              required
              maxlength="255"
              placeholder="What are we building?"
            />
          </label>

          <label class="under span2">
            <span>Description</span>
            <textarea
              v-model="form.description"
              class="u-input"
              rows="2"
              placeholder="One or two sentences — the scope in plain words."
            />
          </label>

          <label class="under">
            <span>Domain</span>
            <select v-model="form.domain" class="u-input">
              <option v-for="d in DOMAINS" :key="d" :value="d">{{ d }}</option>
            </select>
          </label>

          <label class="under">
            <span>Customer</span>
            <input v-model="form.customer" class="u-input" maxlength="255" placeholder="Org name" />
          </label>

          <div class="under" ref="pmAnchor">
            <span class="u-label">
              Project managers
              <em v-if="selectedPms.length" class="u-count">{{ selectedPms.length }}</em>
            </span>

            <div class="pm-composer" :class="{ open: pmMenuOpen }">
              <span
                v-for="u in selectedPms"
                :key="u.id"
                class="pm-chip"
              >
                {{ u.name }}
                <button
                  type="button"
                  class="pm-chip-x"
                  :aria-label="`Remove ${u.name}`"
                  @click="removePm(u)"
                >×</button>
              </span>

              <button
                type="button"
                class="pm-add"
                :aria-label="selectedPms.length ? 'Add another PM' : 'Add a PM'"
                :aria-expanded="pmMenuOpen"
                @click="togglePmMenu"
              >
                <span class="pm-add-plus" aria-hidden="true">+</span>
                <span class="pm-add-label">
                  {{ selectedPms.length ? 'Add PM' : 'Choose project managers' }}
                </span>
              </button>
            </div>

            <div v-if="pmMenuOpen" class="pm-menu" role="listbox">
              <input
                v-model="pmFilter"
                class="pm-search"
                placeholder="Search users…"
                autofocus
              />
              <ul class="pm-options">
                <li v-if="!pmCandidates.length" class="pm-empty">
                  {{ allUsers.length ? 'No matching users.' : 'No users available.' }}
                </li>
                <li
                  v-for="u in pmCandidates"
                  :key="u.id"
                  class="pm-option"
                  role="option"
                  @click="addPm(u)"
                >
                  <span class="pm-avatar" aria-hidden="true">{{ u.name?.[0]?.toUpperCase() || '?' }}</span>
                  <span class="pm-option-name">{{ u.name }}</span>
                  <span v-if="u.email" class="pm-option-email">{{ u.email }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div class="under">
            <span class="u-label">Tags</span>
            <div class="tag-composer" :class="{ has: tags.length }">
              <span v-for="t in tags" :key="t" class="chip">
                {{ t }}
                <button type="button" class="chip-x" @click="removeTag(t)" aria-label="Remove tag">
                  ×
                </button>
              </span>
              <input
                v-model="tagDraft"
                class="chip-input"
                :placeholder="tags.length ? '' : 'Type and press Enter'"
                @keydown="onTagKey"
                @blur="addTagFromDraft"
              />
            </div>
          </div>
        </div>
      </section>

      <hr class="rule" />

      <!-- 02 Planning -->
      <section id="pf-planning" class="sec">
        <header class="sec-head">
          <span class="sec-num mono">02</span>
          <div>
            <div class="sec-eyebrow">Section two</div>
            <h3>Planning</h3>
          </div>
        </header>

        <div class="grid">
          <label class="under">
            <span>Priority</span>
            <select v-model="form.priority" class="u-input">
              <option v-for="[v, l] in PRIORITIES" :key="v" :value="v">{{ l }}</option>
            </select>
          </label>

          <label class="under">
            <span>Fiscal year</span>
            <select v-model="form.fiscalYear" class="u-input">
              <option v-for="y in FYS" :key="y" :value="y">
                {{ y === 'future' ? 'Future' : `FY${y}` }}
              </option>
            </select>
          </label>

          <label class="under value-field">
            <span>Value (THB)</span>
            <input
              v-model="form.value"
              type="number"
              min="0"
              step="100000"
              class="u-input"
              placeholder="0"
            />
            <div class="value-echo mono" aria-hidden="true">
              ฿<span>{{ valueDisplay }}</span>
            </div>
          </label>

          <label class="under">
            <span>Team size</span>
            <input
              v-model="form.teamSize"
              type="number"
              min="1"
              class="u-input"
              placeholder="Optional"
            />
          </label>

          <label class="under">
            <span>Complexity (1–10)</span>
            <input
              v-model="form.complexity"
              type="number"
              min="1"
              max="10"
              class="u-input"
              placeholder="Optional"
            />
          </label>

          <p class="prog-note span2">
            <span class="prog-num mono">Σ</span>
            Team size and complexity feed the Summaries pipeline. Leave blank
            to auto-estimate from assigned PMs and priority.
          </p>
        </div>
      </section>

      <hr class="rule" />

      <!-- 03 Timeline -->
      <section id="pf-timeline" class="sec">
        <header class="sec-head">
          <span class="sec-num mono">03</span>
          <div>
            <div class="sec-eyebrow">Section three</div>
            <h3>Timeline</h3>
          </div>
        </header>

        <div class="grid">
          <label class="under">
            <span>Start date</span>
            <input v-model="form.startDate" type="date" class="u-input" />
          </label>

          <label class="under">
            <span>Due date</span>
            <input v-model="form.dueDate" type="date" class="u-input" />
          </label>

          <p class="prog-note span2">
            <span class="prog-num mono">%</span>
            Progress is derived live from the project's process checklist.
            You don't set it here.
          </p>
        </div>
      </section>
    </div>

    <!-- Sticky action bar -->
    <footer class="pform-foot">
      <div class="foot-meta">
        <span class="foot-eyebrow">Will save as</span>
        <span class="foot-pill ghost">{{ priorityLabel }}</span>
        <span class="foot-sep">/</span>
        <span class="foot-pill ghost mono">{{ fyLabel }}</span>
      </div>
      <div class="foot-actions">
        <button type="button" class="btn ghost" @click="emit('cancel')">Cancel</button>
        <button type="submit" class="btn" :disabled="submitting">
          {{ submitting ? 'Saving…' : (project ? 'Save changes' : 'Create project') }}
        </button>
      </div>
    </footer>
  </form>
</template>

<style scoped>
/* ───── Layout: editorial two-column with sticky footer ───── */
.pform {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 32px;
  align-items: start;
  /* counter the modal-body padding so the footer can be flush */
  margin: -20px;
  padding: 0;
}

/* ───── Sidebar: section index ───── */
.pform-aside {
  position: sticky;
  top: 0;
  align-self: start;
  padding: 28px 0 28px 28px;
  border-right: 1px solid var(--border);
  min-height: 380px;
}
.aside-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--text-dim);
}
.aside-title {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text);
  letter-spacing: -.01em;
  /* allow up to ~2 lines, ellipsize after */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.aside-nav {
  list-style: none;
  margin: 28px 0 0;
  padding: 0;
  display: grid;
  gap: 2px;
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
.aside-nav button {
  width: 100%;
  display: grid;
  grid-template-columns: 28px 1fr;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border: 0;
  background: transparent;
  font: inherit;
  text-align: left;
  color: var(--text-dim);
  cursor: pointer;
  transition: color .15s;
}
.aside-nav button:hover { color: var(--text); }
.aside-nav .num {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .02em;
  color: var(--text-dim);
  transition: color .15s;
}
.aside-nav .lbl {
  font-size: 13px;
  font-weight: 600;
}
.aside-nav button.active { color: var(--text); }
.aside-nav button.active .num { color: var(--accent); }
.aside-nav button.active .lbl {
  position: relative;
}
.aside-nav button.active .lbl::after {
  content: '';
  position: absolute;
  left: -10px; right: 0;
  bottom: -3px;
  height: 2px;
  background: var(--accent);
}
.aside-foot {
  margin-top: 28px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-dim);
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
}
.aside-dot { color: var(--border); }

/* ───── Content stream ───── */
.pform-stream {
  padding: 28px 32px 24px 0;
  display: grid;
  gap: 28px;
}
.sec { display: grid; gap: 18px; }
.sec-head {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  align-items: center;
}
.sec-num {
  font-size: 38px;
  font-weight: 700;
  color: var(--text);
  line-height: 1;
  letter-spacing: -.02em;
}
.sec-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--text-dim);
}
.sec-head h3 {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -.01em;
  color: var(--text);
}
.rule {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 0;
}

/* ───── Grid + underline-style inputs ───── */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px 28px;
}
.span2 { grid-column: 1 / -1; }

.under { display: block; }
.under > span,
.u-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.u-input {
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 6px 0 8px;
  transition: border-color .15s, box-shadow .15s;
}
.u-input.lg {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -.01em;
  padding-bottom: 10px;
}
.u-input:focus {
  outline: none;
  border-bottom-color: var(--accent);
  box-shadow: 0 1px 0 0 var(--accent);
}
.u-input::placeholder { color: var(--text-dim); opacity: .55; }
textarea.u-input { resize: vertical; min-height: 56px; line-height: 1.5; }

/* keep native date arrows tasteful on white */
.u-input[type=date] { color: var(--text); }
.u-input[type=number] { font-variant-numeric: tabular-nums; }

select.u-input {
  appearance: none;
  -webkit-appearance: none;
  /* match the form/modal background so the native popup inherits it */
  background-color: var(--surface);
  background-image:
    linear-gradient(45deg, transparent 50%, var(--text-dim) 50%),
    linear-gradient(135deg, var(--text-dim) 50%, transparent 50%);
  background-position: right 6px top 16px, right 2px top 16px;
  background-size: 4px 4px, 4px 4px;
  background-repeat: no-repeat;
  padding-right: 18px;
}
select.u-input option {
  background-color: var(--surface);
  color: var(--text);
}

/* ───── PM composer (multi-select dropdown) ───── */
.u-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 6px;
  padding: 0 6px;
  height: 14px;
  border-radius: 7px;
  background: var(--accent);
  color: #fff;
  font-size: 9px;
  font-weight: 800;
  font-style: normal;
  letter-spacing: 0;
}

.pm-composer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding: 4px 0 8px;
  transition: border-color .15s;
}
.pm-composer.open { border-bottom-color: var(--accent); }

.pm-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface));
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--border));
  border-radius: 999px;
  padding: 3px 6px 3px 10px;
  font-size: 12px;
  font-weight: 700;
}
.pm-chip-x {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 0;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.pm-chip-x:hover { background: color-mix(in srgb, var(--accent) 22%, transparent); }

.pm-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 6px;
  border: 1px dashed color-mix(in srgb, var(--text-dim) 50%, var(--border));
  border-radius: 999px;
  background: transparent;
  color: var(--text-dim);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: color .15s, border-color .15s, background .15s;
}
.pm-add:hover {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}
.pm-add-plus {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: color-mix(in srgb, currentColor 18%, transparent);
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
}

.pm-menu {
  position: relative;
  margin-top: 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: 5;
  max-height: 280px;
  display: flex;
  flex-direction: column;
}
.pm-search {
  appearance: none;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--border);
  padding: 10px 14px;
  font: inherit;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}
.pm-search:focus { outline: none; }
.pm-options {
  list-style: none;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  flex: 1;
}
.pm-empty {
  padding: 10px 14px;
  color: var(--text-dim);
  font-size: 12px;
  font-style: italic;
}
.pm-option {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}
.pm-option:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
.pm-avatar {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--accent) 18%, var(--surface));
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
}
.pm-option-name { font-weight: 600; }
.pm-option-email {
  color: var(--text-dim);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

/* ───── Tag composer ───── */
.tag-composer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding: 4px 0 8px;
  transition: border-color .15s;
}
.tag-composer:focus-within { border-bottom-color: var(--accent); }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
  border-radius: 999px;
  padding: 2px 4px 2px 10px;
  font-size: 12px;
  font-weight: 600;
}
.chip-x {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 0;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.chip-x:hover { background: color-mix(in srgb, var(--accent) 20%, transparent); }
.chip-input {
  flex: 1;
  min-width: 100px;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 14px;
  color: var(--text);
  padding: 4px 0;
  outline: none;
}
.chip-input::placeholder { color: var(--text-dim); opacity: .55; }

/* ───── Value field with tabular echo ───── */
.value-field { position: relative; }
.value-echo {
  margin-top: 6px;
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: var(--text-dim);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.value-echo span { color: var(--text); font-weight: 600; }

/* ───── Progress note ───── */
.prog-note {
  display: grid;
  grid-template-columns: 22px 1fr;
  align-items: start;
  gap: 10px;
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.6;
  padding-top: 4px;
}
.prog-num {
  font-size: 18px;
  color: var(--accent);
  font-weight: 700;
  line-height: 1;
}

/* ───── Sticky footer action bar ───── */
.pform-foot {
  grid-column: 1 / -1;
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 32px 14px 28px;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--border);
  margin-top: 4px;
}
.foot-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}
.foot-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-right: 4px;
}
.foot-pill {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--text);
  color: var(--surface);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .01em;
}
.foot-pill.ghost {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
}
.foot-sep { color: var(--border); }
.foot-actions {
  display: flex;
  gap: 10px;
}
.foot-actions .btn {
  min-height: 38px;
  padding: 8px 18px;
  font-weight: 700;
  letter-spacing: .01em;
}

/* ───── Responsive ───── */
@media (max-width: 760px) {
  .pform {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .pform-aside {
    position: relative;
    top: auto;
    border-right: 0;
    border-bottom: 1px solid var(--border);
    padding: 20px 18px 14px;
    min-height: 0;
  }
  .aside-title { font-size: 16px; -webkit-line-clamp: 1; }
  .aside-nav {
    margin-top: 14px;
    padding-top: 12px;
    grid-auto-flow: column;
    grid-auto-columns: max-content;
    gap: 10px;
    overflow-x: auto;
  }
  .aside-nav::-webkit-scrollbar { display: none; }
  .aside-nav button {
    grid-template-columns: auto auto;
    gap: 6px;
    padding: 4px 0;
  }
  .aside-foot { display: none; }
  .pform-stream { padding: 18px 18px 8px; gap: 22px; }
  .sec-num { font-size: 30px; }
  .grid { grid-template-columns: 1fr; gap: 18px; }
  .pform-foot {
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
    flex-direction: column-reverse;
    align-items: stretch;
  }
  .foot-actions { justify-content: flex-end; }
  .foot-meta { justify-content: flex-start; }
}
</style>

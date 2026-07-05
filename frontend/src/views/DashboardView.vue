<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useProjectsStore, taskProgress } from '@/stores/projects'
import { useFormat } from '@/composables/useFormat'
import { useProcessChain } from '@/composables/useProcessChain'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api'
import {
  exportProjectSummary, exportProjectSummaryPdf,
  exportRecordsExcel, exportRecordsPdf,
  exportMultiResourceExcel, exportMultiResourcePdf,
  exportProjectPack,
  parseRecordsExcel, parseRecordsExcelMulti,
} from '@/utils/recordExport'
import ExportImportMenu from '@/components/ExportImportMenu.vue'
import ImportResultModal from '@/components/ImportResultModal.vue'

// Local state on purpose: calling store.openDetail/fetchRecords would mutate
// store.current and pop the global ProjectDetail drawer (App.vue).
const store = useProjectsStore()
const ui = useUiStore()
const { date, baht } = useFormat()

const selectedId = ref(null)
const project = ref(null)
const records = ref({
  ptrack: [], bom: [], survey: [], mom: [], verification: [], exceptions: [],
})
const loading = ref(false)

async function loadProject(id) {
  if (!id) { project.value = null; return }
  loading.value = true
  try {
    const [proj, ptrack, bom, survey, mom, verification, exceptions] = await Promise.all([
      api.getProject(id),
      api.listRecords(id, 'ptrack'),
      api.listRecords(id, 'bom'),
      api.listRecords(id, 'survey'),
      api.listRecords(id, 'mom'),
      api.listRecords(id, 'verification'),
      api.listRecords(id, 'exceptions'),
    ])
    project.value = proj
    records.value = {
      ptrack: ptrack.items, bom: bom.items, survey: survey.items,
      mom: mom.items, verification: verification.items, exceptions: exceptions.items,
    }
  } catch (e) {
    ui.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!store.projects.length) await store.fetchAll()
  if (store.projects.length && !selectedId.value) {
    selectedId.value = store.projects[0].id
  }
})

watch(selectedId, (id) => loadProject(id))

const ptrackRows = computed(() => records.value.ptrack || [])
const startDate = computed(() => project.value?.startDate || null)
const { groups, blocker, health } = useProcessChain(ptrackRows, startDate)

// "Wk N – M" derived from cumulativeDays / dayRange so it matches the Excel
// template (e.g. group 1: cum=14, dr=14 → "Wk 1 – 2"; group 2: cum=21, dr=7 → "Wk 3").
function weekLabel(g) {
  const cum = g.cumulativeDays
  const dr = g.dayRange
  if (cum == null || dr == null) return ''
  const prev = cum - dr
  const start = Math.floor(prev / 7) + 1
  const end = Math.ceil(cum / 7)
  return start === end ? `Wk ${start}` : `Wk ${start} – ${end}`
}

const statusEmoji = (s) =>
  s === 'Done' ? '🟢'
    : s === 'In progress' ? '🟡'
    : s === 'Overdue' ? '🔴'
    : '⚪'
const statusKey = (s) =>
  s === 'Done' ? 'done'
    : s === 'In progress' ? 'progress'
    : s === 'Overdue' ? 'overdue'
    : 'not-started'

const pmNames = computed(() => {
  const p = project.value
  if (!p) return '—'
  if (p.pms?.length) return p.pms.map((u) => u.name).join(' / ')
  return p.pm || '—'
})

const progressPct = computed(() => (project.value ? taskProgress(project.value) : 0))
const progressFraction = computed(() => {
  const p = project.value
  if (!p) return '0/0'
  const done = p.processCount ? p.processDone || 0 : p.taskDone || 0
  const total = p.processCount || p.taskCount || 0
  return `${done}/${total}`
})

// ── Section 2 derivations ─────────────────────────────────────────────
const bomRows = computed(() => records.value.bom || [])
const exceptionRows = computed(() => records.value.exceptions || [])

const bomTotal = computed(() =>
  bomRows.value.reduce((a, r) => a + (Number(r.totalPrice) || 0), 0),
)

// Longest-lead supplier — bom row with max leadTime
const longestLead = computed(() => {
  let best = null
  for (const r of bomRows.value) {
    const lt = Number(r.leadTime) || 0
    if (!best || lt > best.lt) best = { lt, supplier: r.supplier || '—', device: r.deviceName }
  }
  return best
})

// Latest customer BOM-confirm date — max dateApprove
const lastBomApprove = computed(() => {
  let max = null
  for (const r of bomRows.value) {
    if (r.dateApprove && (!max || r.dateApprove > max)) max = r.dateApprove
  }
  return max
})

// Value added from change requests — count + concatenated effect notes
const changeRequestSummary = computed(() => {
  const rows = exceptionRows.value
  if (!rows.length) return { count: 0, note: '' }
  const notes = rows
    .map((r) => [r.effectPrice, r.effectTech].filter(Boolean).join(' / '))
    .filter(Boolean)
    .join(' · ')
  return { count: rows.length, note: notes }
})

// ── Section 3 derivations ─────────────────────────────────────────────
// Pick latest row by date desc, fallback to id desc.
function latest(rows) {
  if (!rows?.length) return null
  return [...rows].sort((a, b) => {
    const da = a.date || ''
    const db = b.date || ''
    if (da !== db) return db.localeCompare(da)
    return (b.id || 0) - (a.id || 0)
  })[0]
}

const surveyRows = computed(() => records.value.survey || [])
const momRows = computed(() => records.value.mom || [])
const verificationRows = computed(() => records.value.verification || [])

const latestSurvey = computed(() => latest(surveyRows.value))
const latestMom = computed(() => latest(momRows.value))
const latestVerification = computed(() => latest(verificationRows.value))
const latestException = computed(() => latest(exceptionRows.value))

// ── Export / Import wiring (per section + page-level pack) ────────────
// Dashboard calls `api` directly (not the store) to avoid leaking imported
// rows into the project drawer's `store.records` — same isolation rationale
// as the rest of this view.
const importResultBom = ref(null)
const importingBom = ref(false)
const importResultDocs = ref(null)
const importingDocs = ref(false)
const importResultPtrack = ref(null)
const importingPtrack = ref(false)

async function refreshResource(resource) {
  if (!project.value) return
  const r = await api.listRecords(project.value.id, resource)
  records.value = { ...records.value, [resource]: r.items }
}

async function importRows(resource, rows) {
  for (const rec of rows) {
    await api.createRecord(project.value.id, resource, rec)
  }
}

// Section 1 — Executive Summary (export-only cover sheet)
async function exportSec1(format) {
  if (!project.value) return
  try {
    if (format === 'excel') await exportProjectSummary(project.value)
    else exportProjectSummaryPdf(project.value)
    ui.success(`Exported Executive Summary to ${format === 'excel' ? 'Excel' : 'PDF'}`)
  } catch (e) { ui.error(e.message) }
}

// Section 2 — BOM
async function exportSec2(format) {
  if (!bomRows.value.length) return
  try {
    const name = project.value?.name || ''
    if (format === 'excel') await exportRecordsExcel('bom', bomRows.value, name)
    else exportRecordsPdf('bom', bomRows.value, name)
    ui.success(`Exported ${bomRows.value.length} BOM record(s) to ${format === 'excel' ? 'Excel' : 'PDF'}`)
  } catch (e) { ui.error(e.message) }
}
async function parseSec2(file) {
  try { importResultBom.value = await parseRecordsExcel('bom', file) }
  catch (e) { ui.error(e.message) }
}
async function confirmSec2() {
  const valid = importResultBom.value?.valid || []
  if (!valid.length) return
  importingBom.value = true
  try {
    await importRows('bom', valid)
    await refreshResource('bom')
    ui.success(`Imported ${valid.length} BOM record(s)`)
    importResultBom.value = null
  } catch (e) { ui.error(e.message) }
  finally { importingBom.value = false }
}

// Section 3 — Document Intelligence (multi-sheet: survey / mom / verification / exceptions)
const DOC_RESOURCES = ['survey', 'mom', 'verification', 'exceptions']
const docsHasRows = computed(() =>
  DOC_RESOURCES.some((r) => (records.value[r] || []).length > 0),
)
async function exportSec3(format) {
  if (!docsHasRows.value) return
  const specs = DOC_RESOURCES.map((r) => ({ resource: r, rows: records.value[r] || [] }))
  const base = ['documents', slugForFile(project.value?.name), stampForFile()].filter(Boolean).join('-')
  try {
    if (format === 'excel') {
      await exportMultiResourceExcel(specs, `${base}.xlsx`)
    } else {
      const title = `Document Intelligence — ${project.value?.name || ''}`.trim()
      exportMultiResourcePdf(specs, `${base}.pdf`, title)
    }
    ui.success(`Exported Document Intelligence to ${format === 'excel' ? 'Excel' : 'PDF'}`)
  } catch (e) { ui.error(e.message) }
}
async function parseSec3(file) {
  try { importResultDocs.value = await parseRecordsExcelMulti(DOC_RESOURCES, file) }
  catch (e) { ui.error(e.message) }
}
async function confirmSec3() {
  const per = importResultDocs.value?.perResource || {}
  const total = Object.values(per).reduce((a, x) => a + (x.valid?.length || 0), 0)
  if (!total) return
  importingDocs.value = true
  try {
    for (const r of DOC_RESOURCES) {
      const valid = per[r]?.valid || []
      if (!valid.length) continue
      await importRows(r, valid)
      await refreshResource(r)
    }
    ui.success(`Imported ${total} document record(s)`)
    importResultDocs.value = null
  } catch (e) { ui.error(e.message) }
  finally { importingDocs.value = false }
}

// Section 4 — Process Checklist (ptrack)
async function exportSec4(format) {
  if (!ptrackRows.value.length) return
  try {
    const name = project.value?.name || ''
    if (format === 'excel') await exportRecordsExcel('ptrack', ptrackRows.value, name)
    else exportRecordsPdf('ptrack', ptrackRows.value, name)
    ui.success(`Exported ${ptrackRows.value.length} process record(s) to ${format === 'excel' ? 'Excel' : 'PDF'}`)
  } catch (e) { ui.error(e.message) }
}
async function parseSec4(file) {
  try { importResultPtrack.value = await parseRecordsExcel('ptrack', file) }
  catch (e) { ui.error(e.message) }
}
async function confirmSec4() {
  const valid = importResultPtrack.value?.valid || []
  if (!valid.length) return
  importingPtrack.value = true
  try {
    await importRows('ptrack', valid)
    // Reload the whole project so week-grouping + health recompute cleanly.
    await loadProject(selectedId.value)
    ui.success(`Imported ${valid.length} process record(s)`)
    importResultPtrack.value = null
  } catch (e) { ui.error(e.message) }
  finally { importingPtrack.value = false }
}

// Page-level — Full project pack
async function exportPack() {
  if (!project.value) return
  try {
    await exportProjectPack(project.value, records.value)
    ui.success('Exported full project pack')
  } catch (e) { ui.error(e.message) }
}

// Local helpers mirroring recordExport.js's slug/stamp so filenames line up.
function slugForFile(s) {
  return String(s || '').trim().replace(/[^\w\u0E00-\u0E7F-]+/g, '_').replace(/^_+|_+$/g, '')
}
function stampForFile() {
  return new Date().toISOString().slice(0, 10)
}

const docSummaries = computed(() => [
  {
    key: 'survey',
    icon: '📍',
    impact: latestSurvey.value?.limitation ? '⚠️' : '',
    labelTh: 'Site Survey · สำรวจหน้างาน',
    labelEn: 'Site Survey',
    date: latestSurvey.value?.date,
    line: latestSurvey.value
      ? (latestSurvey.value.limitation
          ? `ข้อจำกัด: ${latestSurvey.value.limitation}`
          : latestSurvey.value.issue
            ? `ปัญหา: ${latestSurvey.value.issue}`
            : latestSurvey.value.result || latestSurvey.value.conclude || '')
      : '',
    count: surveyRows.value.length,
  },
  {
    key: 'verification',
    icon: '📍',
    impact: latestVerification.value?.status ? '✅' : (latestVerification.value?.defected ? '⚠️' : ''),
    labelTh: 'Verify Solution · ทดสอบระบบ',
    labelEn: 'Verify Solution',
    date: latestVerification.value?.date,
    line: latestVerification.value
      ? `${latestVerification.value.status ? 'Approved' : 'Pending'}${latestVerification.value.defected ? ` (พบปัญหา: ${latestVerification.value.defected})` : ''}`
      : '',
    count: verificationRows.value.length,
  },
  {
    key: 'mom',
    icon: '📍',
    impact: latestMom.value?.todo ? '📌' : '',
    labelTh: 'Customer MoM · ประชุมลูกค้า',
    labelEn: 'Customer MoM',
    date: latestMom.value?.date,
    line: latestMom.value
      ? (latestMom.value.todo
          ? `Action: ${latestMom.value.todo}`
          : latestMom.value.conclude || latestMom.value.concerns || '')
      : '',
    count: momRows.value.length,
  },
  {
    key: 'exceptions',
    icon: '📍',
    impact: exceptionRows.value.length ? '🔴' : '',
    labelTh: 'Exception Log · บันทึกขอแก้ไข',
    labelEn: 'Exception Log',
    date: latestException.value?.date,
    line: exceptionRows.value.length
      ? `แจ้งแก้ ${exceptionRows.value.length} ข้อ${latestException.value?.effectTech ? ` (ผลกระทบ: ${latestException.value.effectTech})` : ''}`
      : '',
    count: exceptionRows.value.length,
  },
])
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Executive view</div>
        <h1 class="page-title">Dashboard · แดชบอร์ดโครงการ</h1>
        <p class="page-subtitle">
          สรุปภาพรวม, ต้นทุน, เอกสารย่อย และ Solution process
        </p>
      </div>
    </header>

    <div class="selector card">
      <label for="proj-select">
        <span class="lbl">โครงการ · Project</span>
        <select id="proj-select" v-model="selectedId">
          <option v-if="!store.projects.length" :value="null">— ไม่มีโครงการ · None —</option>
          <option v-for="p in store.projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>
      <button class="btn pack-btn" :disabled="!project" @click="exportPack">
        Full project pack (.xlsx)
      </button>
    </div>

    <div v-if="loading" class="empty">Loading…</div>

    <template v-else-if="project">
      <!-- ── Section 1 — Executive Summary & Project Health ───────────────── -->
      <section class="card section">
        <div class="section-head">
          <div>
            <div class="section-kicker">📌 1. Executive Summary &amp; Project Health</div>
            <h2>สรุปภาพรวมและสถานะโครงการ</h2>
          </div>
          <ExportImportMenu
            :formats="['excel', 'pdf']"
            :rows="project ? -1 : 0"
            @export="exportSec1"
          />
        </div>
        <div class="sec1-grid">
          <div class="field">
            <div class="lbl">ชื่อโครงการ · Project</div>
            <div class="val strong">{{ project.name }}</div>
          </div>
          <div class="field">
            <div class="lbl">ความสำเร็จ · Progress</div>
            <div class="val mono">{{ progressPct }}% ({{ progressFraction }} งาน)</div>
            <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPct + '%' }" /></div>
          </div>
          <div class="field">
            <div class="lbl">ผู้จัดการ · PM</div>
            <div class="val">{{ pmNames }}</div>
          </div>
          <div class="field">
            <div class="lbl">สถานะโครงการ · Health</div>
            <div>
              <span class="health" :class="health.key">
                <span class="dot" /> {{ health.emoji }} {{ health.label }}
              </span>
            </div>
          </div>
          <div class="field">
            <div class="lbl">กำหนดส่ง Proposal · Proposal Due</div>
            <div class="val mono">{{ project.dueDate ? date(project.dueDate) : '—' }}</div>
          </div>
          <div class="field">
            <div class="lbl">คอขวดปัจจุบัน · Bottle neck</div>
            <div class="val blocker">
              <span v-if="blocker">⏳ {{ blocker.label }}</span>
              <span v-else class="dim">— ไม่มี · None</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Section 2 — Cost & Procurement Insights ──────────────────────── -->
      <section class="card section">
        <div class="section-head">
          <div>
            <div class="section-kicker">💰 2. Cost &amp; Procurement Insights</div>
            <h2>ข้อมูลต้นทุนและความเสี่ยงจัดซื้อ</h2>
          </div>
          <ExportImportMenu
            :formats="['excel', 'pdf']"
            :rows="bomRows.length"
            import-enabled
            @export="exportSec2"
            @import-file="parseSec2"
          />
        </div>
        <div class="sec1-grid">
          <div class="field">
            <div class="lbl">ต้นทุนรวม จาก BOM · Total Cost (BOM)</div>
            <div class="val strong mono readout">{{ baht(bomTotal) }}</div>
            <div class="sub">{{ bomRows.length }} รายการ · {{ bomRows.length }} item{{ bomRows.length === 1 ? '' : 's' }}</div>
          </div>
          <div class="field">
            <div class="lbl">มูลค่าโครงการ · Project Value</div>
            <div class="val strong mono readout">{{ baht(project.value || 0) }}</div>
            <div class="sub">จากข้อมูลโครงการ · From project record</div>
          </div>
          <div class="field">
            <div class="lbl">ซัพพลายเออร์ที่รอนานสุด · Longest-Lead Supplier</div>
            <div v-if="longestLead" class="val">
              <span class="strong">{{ longestLead.supplier }}</span>
              <span class="lt-pill">{{ longestLead.lt }} วัน · {{ longestLead.lt }} day{{ longestLead.lt === 1 ? '' : 's' }}</span>
            </div>
            <div v-else class="val dim">— ไม่มี · None</div>
            <div v-if="longestLead?.device" class="sub">{{ longestLead.device }}</div>
          </div>
          <div class="field">
            <div class="lbl">วันลูกค้ายืนยัน BOM · Customer BOM Approval</div>
            <div class="val mono">{{ lastBomApprove ? date(lastBomApprove) : '—' }}</div>
            <div v-if="lastBomApprove" class="sub">วันที่ล่าสุดที่ลูกค้ายืนยัน · Latest approval date</div>
          </div>
          <div class="field span-2">
            <div class="lbl">มูลค่าที่เพิ่มมาจากการขอแก้ไข · Value Added from Change Requests</div>
            <div v-if="changeRequestSummary.count" class="val">
              <span class="strong">เพิ่มขึ้น: {{ changeRequestSummary.count }} รายการ · {{ changeRequestSummary.count }} change{{ changeRequestSummary.count === 1 ? '' : 's' }}</span>
            </div>
            <div v-else class="val dim">เพิ่มขึ้น: 0 · No change requested</div>
            <div v-if="changeRequestSummary.note" class="sub note">{{ changeRequestSummary.note }}</div>
          </div>
        </div>
      </section>

      <!-- ── Section 3 — Document Intelligence ────────────────────────────── -->
      <section class="card section">
        <div class="section-head">
          <div>
            <div class="section-kicker">📑 3. Document Intelligence</div>
            <h2>ข้อมูลเชิงลึกจากเอกสารย่อยหน้างาน</h2>
          </div>
          <ExportImportMenu
            :formats="['excel', 'pdf']"
            :rows="docsHasRows ? -1 : 0"
            import-enabled
            @export="exportSec3"
            @import-file="parseSec3"
          />
        </div>
        <ul class="doc-list">
          <li v-for="d in docSummaries" :key="d.key">
            <div class="doc-head">
              <span class="doc-icon">{{ d.icon }}</span>
              <span class="doc-label">{{ d.labelTh }}</span>
              <span v-if="d.count > 1" class="doc-count">×{{ d.count }}</span>
              <span v-if="d.date" class="doc-date mono">{{ date(d.date) }}</span>
            </div>
            <div class="doc-line">
              <template v-if="d.line">
                <span v-if="d.impact" class="doc-impact">{{ d.impact }}</span>
                {{ d.line }}
              </template>
              <span v-else class="dim">— ไม่มีบันทึก · No record</span>
            </div>
          </li>
        </ul>
      </section>

      <!-- ── Section 4 — Solution Process──────────────────────── -->
      <section class="card section">
        <div class="section-head">
          <div>
            <div class="section-kicker">📋 4. Solution Process</div>
            <h2>กระบวนการทำงาน Solution</h2>
          </div>
          <div class="head-right">
            <div v-if="groups.length" class="matrix-meta mono">
              {{ ptrackRows.length }} steps · {{ progressFraction }} done
            </div>
            <ExportImportMenu
              :formats="['excel', 'pdf']"
              :rows="ptrackRows.length"
              import-enabled
              @export="exportSec4"
              @import-file="parseSec4"
            />
          </div>
        </div>

        <div v-if="groups.length" class="matrix-wrap">
          <table class="matrix">
            <thead>
              <tr>
                <th>สัปดาห์ · Wk</th>
                <th>รายละเอียดขั้นตอน · SOP</th>
                <th>ผู้รับผิดชอบ · Responsible</th>
                <th>วันเริ่มงาน · Start</th>
                <th>กำหนดส่ง · Due</th>
                <th>สถานะงาน · Status</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="g in groups" :key="g.process">
                <tr class="group-row">
                  <td colspan="6">
                    <span class="g-num">{{ weekLabel(g) || '—' }}</span>
                    <span class="g-name">{{ g.process }}</span>
                    <span class="g-count">{{ g.done }}/{{ g.items.length }}</span>
                  </td>
                </tr>
                <tr v-for="r in g.items" :key="r.id" :class="['step-row', statusKey(r._status)]">
                  <td class="mono dim">{{ weekLabel(g) }}</td>
                  <td>{{ r.task || '—' }}</td>
                  <td>{{ r.pm || '—' }}</td>
                  <td class="mono">{{ g.startDate ? date(g.startDate) : '—' }}</td>
                  <td class="mono">{{ g.dueDate ? date(g.dueDate) : '—' }}</td>
                  <td>
                    <span class="status-pill" :class="statusKey(r._status)">
                      <span class="dot" /> {{ statusEmoji(r._status) }} {{ r._status }}
                    </span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <div v-else class="empty matrix-empty">
          — ยังไม่มี ptrack สำหรับโครงการนี้ · No process checklist for this project yet
        </div>
      </section>
    </template>

    <div v-else class="empty">เลือกโครงการเพื่อดูข้อมูล · Select a project to view details</div>

    <ImportResultModal
      v-if="importResultBom"
      title="Import BOM"
      :result="importResultBom"
      :importing="importingBom"
      @close="importResultBom = null"
      @confirm="confirmSec2"
    />
    <ImportResultModal
      v-if="importResultDocs"
      title="Import Documents"
      :result="importResultDocs"
      :importing="importingDocs"
      @close="importResultDocs = null"
      @confirm="confirmSec3"
    />
    <ImportResultModal
      v-if="importResultPtrack"
      title="Import Process Checklist"
      :result="importResultPtrack"
      :importing="importingPtrack"
      @close="importResultPtrack = null"
      @confirm="confirmSec4"
    />
  </div>
</template>

<style scoped>
.view { font-family: var(--font); }
.selector {
  padding: 14px 18px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.selector label { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; flex: 1; min-width: 280px; }
.pack-btn { white-space: nowrap; }
.selector .lbl { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-dim); font-weight: 700; }
.selector select {
  flex: 1; min-width: 280px; padding: 8px 12px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface);
  color: var(--text); font-family: var(--font); font-size: 13px;
}
.section { padding: 18px; margin-bottom: 16px; }
.section-head {
  margin-bottom: 4px;
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap;
}
.head-right { display: inline-flex; align-items: center; gap: 12px; }
.section-kicker { font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: .05em; text-transform: uppercase; }
.section h2 { font-size: 16px; margin: 4px 0 0; }
.sec1-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px;
  margin-top: 16px;
}
.field { display: grid; gap: 4px; }
.field .lbl { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--text-dim); }
.field .val { font-size: 14px; color: var(--text); }
.field .val.strong { font-weight: 700; font-size: 15px; }
.field .val.dim { color: var(--text-dim); }
.progress-bar { height: 6px; background: var(--bg-sunken); border-radius: 999px; overflow: hidden; margin-top: 6px; max-width: 320px; }
.progress-fill { height: 100%; background: var(--accent); transition: width .2s ease; }
.health {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 700;
  border: 1px solid currentColor;
}
.health.ontrack { color: var(--success); background: color-mix(in srgb, var(--success) 12%, transparent); }
.health.watch { color: var(--warning); background: color-mix(in srgb, var(--warning) 12%, transparent); }
.health.risk { color: var(--danger); background: color-mix(in srgb, var(--danger) 12%, transparent); }
.health.unknown { color: var(--text-dim); background: var(--bg-sunken); border-color: var(--border); }
.health .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.blocker { font-size: 13px; font-weight: 600; }
.field .sub { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.field .sub.note { font-style: italic; }
.field.span-2 { grid-column: span 2; }
@media (max-width: 640px) { .field.span-2 { grid-column: span 1; } }
.lt-pill {
  display: inline-block; margin-left: 8px;
  font-size: 11px; font-weight: 700; padding: 2px 8px;
  border-radius: 999px; background: color-mix(in srgb, var(--warning) 14%, transparent);
  color: var(--warning); font-variant-numeric: tabular-nums;
}
.doc-list { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 14px; }
.doc-list li {
  padding: 12px 14px; background: var(--bg-sunken);
  border: 1px solid var(--border); border-radius: 8px;
}
.doc-head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
  color: var(--text-dim); font-weight: 700; margin-bottom: 4px;
}
.doc-icon { font-size: 13px; }
.doc-label { color: var(--text); }
.doc-count {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  background: var(--surface); color: var(--text-dim); border: 1px solid var(--border);
}
.doc-date { margin-left: auto; color: var(--text-dim); text-transform: none; letter-spacing: 0; }
.doc-line { font-size: 13px; color: var(--text); line-height: 1.45; }
.doc-impact { margin-right: 4px; }
.dim { color: var(--text-dim); font-style: italic; }

/* ── Section 4 matrix ─────────────────────────────────────────────── */
.matrix-meta { font-size: 12px; color: var(--text-dim); font-weight: 700; }
.matrix-wrap { margin-top: 12px; overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
.matrix { width: 100%; border-collapse: collapse; font-size: 12.5px; min-width: 720px; }
.matrix th, .matrix td { padding: 9px 12px; text-align: left; vertical-align: middle; }
.matrix thead th {
  background: var(--bg-sunken);
  font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-dim); font-weight: 700;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.matrix tbody tr + tr { border-top: 1px solid var(--border); }
.group-row td {
  background: color-mix(in srgb, var(--accent) 6%, var(--bg-sunken));
  font-size: 11px; text-transform: uppercase; letter-spacing: .04em; font-weight: 700;
  padding: 7px 12px;
}
.group-row .g-num { color: var(--accent); margin-right: 10px; font-variant-numeric: tabular-nums; }
.group-row .g-name { color: var(--text); }
.group-row .g-count { color: var(--text-dim); margin-left: 10px; }
.step-row td { color: var(--text); }
.step-row td.dim { color: var(--text-dim); }
.status-pill {
  --c: var(--text-dim);
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 10px; font-weight: 800; padding: 3px 10px 3px 8px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--c) 35%, var(--border));
  background: color-mix(in srgb, var(--c) 10%, transparent);
  color: var(--c);
  letter-spacing: .04em; text-transform: uppercase; white-space: nowrap;
}
.status-pill.done        { --c: var(--success); }
.status-pill.progress    { --c: var(--warning); }
.status-pill.overdue     { --c: var(--danger); }
.status-pill.not-started { --c: var(--text-dim); }
.status-pill .dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--c);
  box-shadow: 0 0 0 2.5px color-mix(in srgb, var(--c) 20%, transparent);
}
.matrix-empty { padding: 20px; }
.empty { padding: 32px; text-align: center; color: var(--text-dim); font-size: 13px; }
</style>

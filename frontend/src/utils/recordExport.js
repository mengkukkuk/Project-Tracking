// Schema-driven import/export for the per-project record tabs
// (survey, mom, bom, verification, exceptions). Shared by RecordList.vue so
// every tab gets Excel/PDF export + Excel import from one implementation.
// Also used by DashboardView.vue for per-section + project-pack workbooks.
//
// Standards follow Project-Tracking/im-ex-skills.md:
//  - Excel via exceljs: styled/filtered header, typed date/number cells, auto-fit widths.
//  - PDF via jspdf + jspdf-autotable: repeating header, "Page X of Y", timestamp,
//    embedded IBM Plex Sans Thai so Thai content renders.
//  - Import: extension/size validation, case-insensitive header mapping,
//    formula-injection sanitization, structured per-row error report.

import ExcelJS from 'exceljs'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { RECORD_SCHEMAS } from '@/schemas/records'
import { registerThaiFont } from '@/assets/fonts/IBMPlexSansThai'
import { taskProgress } from '@/stores/projects'

// Format a YYYY-MM-DD record date for display as Thai-local DD/MM/YYYY.
// Pure string parse — avoids `new Date(iso)` which interprets ISO as UTC and
// would shift the day in negative-offset zones.
function formatDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  if (!m) return ''
  return `${m[3]}/${m[2]}/${m[1]}`
}

const MAX_IMPORT_BYTES = 10 * 1024 * 1024 // 10MB
const TRUTHY = new Set(['true', '1', 'yes', 'y', '✓', 'x', 'passed', 'done'])

// All fields of a record type (not just the visible table columns) so exports
// carry the full record and round-trip cleanly back through import.
function fieldsFor(resource) {
  const schema = RECORD_SCHEMAS[resource]
  if (!schema) throw new Error(`Unknown record type: ${resource}`)
  return schema.fields
}

function stamp() {
  return new Date().toISOString().slice(0, 10)
}

function slug(s) {
  return String(s || '').trim().replace(/[^\w\u0E00-\u0E7F-]+/g, '_').replace(/^_+|_+$/g, '')
}

// Parse "YYYY-MM-DD" into a UTC-midnight Date. ExcelJS serializes JS Dates to
// Excel serial numbers using their UTC components, so passing a local-midnight
// Date causes a one-day shift in non-UTC zones (e.g. in +07:00, local
// 2026-01-15 00:00 is 2026-01-14 17:00 UTC and is written as Jan 14).
// Pair with UTC-based readback in normalizeDate() so the round-trip is exact.
function isoToExcelDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso))
  if (!m) return null
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// Mirror the on-screen table formatting (RecordList.vue display()).
function displayValue(field, v) {
  if (field.type === 'checkbox') return v ? '✓' : '—'
  if (field.type === 'date') return v ? formatDate(v) : '—'
  if (field.type === 'number') return v == null ? '—' : Number(v).toLocaleString()
  return v == null || v === '' ? '—' : String(v)
}

// Ensure every sheet name in a workbook is unique (Excel limit) + ≤31 chars.
function dedupeSheetName(wb, base) {
  const clip = (s) => s.slice(0, 31)
  const name = clip(base || 'Sheet')
  if (!wb.getWorksheet(name)) return name
  for (let i = 2; i < 1000; i++) {
    const suffix = ` (${i})`
    const candidate = clip(base.slice(0, 31 - suffix.length)) + suffix
    if (!wb.getWorksheet(candidate)) return candidate
  }
  return name
}

// ---------------------------------------------------------------------------
// Internal: populate a worksheet for one resource (no workbook creation, no
// download). Reused by single- and multi-resource Excel exports.
// ---------------------------------------------------------------------------
function addRecordSheet(wb, resource, rows, sheetName) {
  const schema = RECORD_SCHEMAS[resource]
  const fields = fieldsFor(resource)
  const ws = wb.addWorksheet(dedupeSheetName(wb, sheetName || schema.label))

  ws.columns = fields.map((f) => ({ header: f.label, key: f.key, width: 16 }))

  for (const row of rows) {
    const cells = {}
    for (const f of fields) {
      const v = row[f.key]
      if (f.type === 'date') cells[f.key] = isoToExcelDate(v)
      else if (f.type === 'number') cells[f.key] = v == null || v === '' ? null : Number(v)
      else if (f.type === 'checkbox') cells[f.key] = !!v
      else cells[f.key] = v ?? ''
    }
    ws.addRow(cells)
  }

  // Type-specific number formats.
  fields.forEach((f, i) => {
    const col = ws.getColumn(i + 1)
    if (f.type === 'date') col.numFmt = 'dd/mm/yyyy'
    else if (f.type === 'number') col.numFmt = '#,##0'
  })

  // Header styling + auto-filter + freeze.
  const header = ws.getRow(1)
  header.font = { bold: true, color: { argb: 'FFFFFFFF' } }
  header.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }
  header.alignment = { vertical: 'middle' }
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: fields.length } }
  ws.views = [{ state: 'frozen', ySplit: 1 }]

  // Auto-fit column widths from longest cell.
  ws.columns.forEach((column) => {
    let max = 0
    column.eachCell({ includeEmpty: true }, (cell) => {
      const len = cell.value == null ? 0 : String(cell.value).length
      if (len > max) max = len
    })
    column.width = Math.min(Math.max(max + 4, 12), 60)
  })

  return ws
}

async function writeAndDownload(wb, filename) {
  const buffer = await wb.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  triggerDownload(blob, filename)
}

// ---------------------------------------------------------------------------
// Excel export — single resource (used by RecordList.vue, signature unchanged)
// ---------------------------------------------------------------------------
export async function exportRecordsExcel(resource, rows, projectName = '') {
  const schema = RECORD_SCHEMAS[resource]
  const wb = new ExcelJS.Workbook()
  addRecordSheet(wb, resource, rows)
  const parts = [slug(schema.label), slug(projectName), stamp()].filter(Boolean)
  await writeAndDownload(wb, `${parts.join('-')}.xlsx`)
}

// ---------------------------------------------------------------------------
// Excel export — multi-resource (one workbook, multiple sheets)
// `specs`: [{ resource, rows, sheetName? }, ...]. Empty `rows` are skipped.
// ---------------------------------------------------------------------------
export async function exportMultiResourceExcel(specs, filename) {
  const wb = new ExcelJS.Workbook()
  let added = 0
  for (const { resource, rows, sheetName } of specs) {
    if (!rows || !rows.length) continue
    addRecordSheet(wb, resource, rows, sheetName)
    added++
  }
  if (!added) throw new Error('No data to export.')
  await writeAndDownload(wb, filename)
}

// ---------------------------------------------------------------------------
// Project summary cover sheet
// ---------------------------------------------------------------------------
function projectSummaryRows(project) {
  const pmNames = project.pms?.length
    ? project.pms.map((u) => u.name).join(' / ')
    : project.pm || ''
  const progress = `${taskProgress(project)}%`
  const taskFrac = `${project.taskDone || 0}/${project.taskCount || 0}`
  const procFrac = `${project.processDone || 0}/${project.processCount || 0}`
  return [
    ['Project', project.name || ''],
    ['Code', project.code || ''],
    ['Customer', project.customer || ''],
    ['Domain', project.domain || ''],
    ['Status', project.status || ''],
    ['Priority', project.priority || ''],
    ['Fiscal year', project.fiscalYear || ''],
    ['Value', project.value == null ? '' : Number(project.value)],
    ['Start date', project.startDate || ''],
    ['Due date', project.dueDate || ''],
    ['Project managers', pmNames],
    ['Description', project.description || ''],
    ['Progress', progress],
    ['Tasks (done/total)', taskFrac],
    ['Process (done/total)', procFrac],
  ]
}

// Add a 2-column "Project Summary" sheet to a workbook.
export function addProjectSummarySheet(wb, project) {
  const ws = wb.addWorksheet(dedupeSheetName(wb, 'Project Summary'))
  ws.columns = [
    { header: 'Field', key: 'field', width: 24 },
    { header: 'Value', key: 'value', width: 60 },
  ]
  for (const [label, value] of projectSummaryRows(project)) {
    if (label === 'Start date' || label === 'Due date') {
      const d = value ? isoToExcelDate(value) : null
      const row = ws.addRow({ field: label, value: d })
      row.getCell(2).numFmt = 'dd/mm/yyyy'
    } else if (label === 'Value') {
      const row = ws.addRow({ field: label, value })
      row.getCell(2).numFmt = '#,##0'
    } else {
      ws.addRow({ field: label, value })
    }
  }

  const header = ws.getRow(1)
  header.font = { bold: true, color: { argb: 'FFFFFFFF' } }
  header.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }
  header.alignment = { vertical: 'middle' }
  ws.views = [{ state: 'frozen', ySplit: 1 }]

  for (let r = 2; r <= ws.rowCount; r++) {
    ws.getCell(`A${r}`).font = { bold: true }
    ws.getCell(`B${r}`).alignment = { wrapText: true, vertical: 'top' }
  }
  return ws
}

// Section 1 (export-only): 1-sheet workbook with project cover sheet.
export async function exportProjectSummary(project, filename) {
  const wb = new ExcelJS.Workbook()
  addProjectSummarySheet(wb, project)
  const name =
    filename || `${['summary', slug(project.name), stamp()].filter(Boolean).join('-')}.xlsx`
  await writeAndDownload(wb, name)
}

// Section 1 (export-only): same cover-sheet content as a PDF.
export function exportProjectSummaryPdf(project) {
  const doc = new jsPDF({ orientation: 'portrait', format: 'a4' })
  const font = registerThaiFont(doc)
  const title = `Project Summary — ${project.name || ''}`.trim()
  const printed = new Date().toLocaleString('en-GB')

  const body = projectSummaryRows(project).map(([label, value]) => {
    let display = value
    if (label === 'Start date' || label === 'Due date') display = value ? formatDate(value) : '—'
    else if (label === 'Value')
      display = value == null || value === '' ? '—' : Number(value).toLocaleString()
    else if (display == null || display === '') display = '—'
    return [label, String(display)]
  })

  autoTable(doc, {
    head: [['Field', 'Value']],
    body,
    startY: 56,
    margin: { top: 56, bottom: 28, left: 28, right: 28 },
    styles: { font, fontStyle: 'normal', fontSize: 9, overflow: 'linebreak', cellPadding: 4 },
    headStyles: { font, fillColor: [79, 129, 189], textColor: 255, fontSize: 9 },
    columnStyles: { 0: { cellWidth: 140 } },
    didDrawPage: () => {
      doc.setFont(font)
      doc.setFontSize(13)
      doc.text(title, 28, 34)
      doc.setFontSize(8)
      doc.text(`Generated ${printed}`, 28, 46)
    },
  })

  const total = doc.internal.getNumberOfPages()
  const w = doc.internal.pageSize.getWidth()
  const h = doc.internal.pageSize.getHeight()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setFont(font)
    doc.setFontSize(8)
    doc.text(`Page ${i} of ${total}`, w - 28, h - 14, { align: 'right' })
  }
  doc.save(`${['summary', slug(project.name), stamp()].filter(Boolean).join('-')}.pdf`)
}

// ---------------------------------------------------------------------------
// PDF export — single resource (used by RecordList.vue, signature unchanged)
// ---------------------------------------------------------------------------
export function exportRecordsPdf(resource, rows, projectName = '') {
  const schema = RECORD_SCHEMAS[resource]
  const title = projectName ? `${schema.label} — ${projectName}` : schema.label
  const parts = [slug(schema.label), slug(projectName), stamp()].filter(Boolean)
  _writePdfDoc([{ resource, rows, title: schema.label }], title, `${parts.join('-')}.pdf`, false)
}

// ---------------------------------------------------------------------------
// PDF export — multi-resource (single document, one autoTable per resource,
// shared header/footer). Used for Section 3.
// `specs`: [{ resource, rows, title? }, ...]. Empty `rows` are skipped.
// ---------------------------------------------------------------------------
export function exportMultiResourcePdf(specs, filename, docTitle) {
  const filled = specs.filter((s) => s.rows && s.rows.length)
  if (!filled.length) throw new Error('No data to export.')
  _writePdfDoc(filled, docTitle, filename, true)
}

function _writePdfDoc(specs, docTitle, filename, sectionizeTitle) {
  const doc = new jsPDF({ orientation: 'landscape', format: 'a4' })
  const font = registerThaiFont(doc)
  const printed = new Date().toLocaleString('en-GB')
  let currentTitle = docTitle || ''

  specs.forEach((spec, idx) => {
    const schema = RECORD_SCHEMAS[spec.resource]
    const fields = fieldsFor(spec.resource)
    const head = [fields.map((f) => f.label)]
    const body = spec.rows.map((row) => fields.map((f) => displayValue(f, row[f.key])))
    if (idx > 0) doc.addPage()
    currentTitle = sectionizeTitle
      ? `${docTitle || ''}${docTitle ? ' — ' : ''}${spec.title || schema.label}`
      : docTitle || schema.label

    autoTable(doc, {
      head,
      body,
      startY: 56,
      margin: { top: 56, bottom: 28, left: 28, right: 28 },
      styles: { font, fontStyle: 'normal', fontSize: 8, overflow: 'linebreak', cellPadding: 3 },
      headStyles: { font, fillColor: [79, 129, 189], textColor: 255, fontSize: 8 },
      didDrawPage: () => {
        doc.setFont(font)
        doc.setFontSize(13)
        doc.text(currentTitle, 28, 34)
        doc.setFontSize(8)
        doc.text(`Generated ${printed}`, 28, 46)
      },
    })
  })

  const total = doc.internal.getNumberOfPages()
  const w = doc.internal.pageSize.getWidth()
  const h = doc.internal.pageSize.getHeight()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setFont(font)
    doc.setFontSize(8)
    doc.text(`Page ${i} of ${total}`, w - 28, h - 14, { align: 'right' })
  }
  doc.save(filename)
}

// ---------------------------------------------------------------------------
// Full project pack: cover sheet + every non-empty resource as its own sheet.
// `recordsByResource`: { [resource]: rows[] }
// ---------------------------------------------------------------------------
export async function exportProjectPack(project, recordsByResource, filename) {
  const wb = new ExcelJS.Workbook()
  addProjectSummarySheet(wb, project)

  for (const resource of Object.keys(RECORD_SCHEMAS)) {
    const rows = recordsByResource[resource]
    if (!rows || !rows.length) continue
    addRecordSheet(wb, resource, rows)
  }

  const name =
    filename || `${['project-pack', slug(project.name), stamp()].filter(Boolean).join('-')}.xlsx`
  await writeAndDownload(wb, name)
}

// ---------------------------------------------------------------------------
// Project-list exports (Table view)
// Projects aren't a "record resource" (no RECORD_SCHEMAS entry) so this is a
// separate code path with its own column definition.
// ---------------------------------------------------------------------------
const PROJECT_COLUMNS = [
  { key: 'domain',     label: 'Domain',      type: 'text' },
  { key: 'name',       label: 'Name',        type: 'text' },
  { key: 'code',       label: 'Code',        type: 'text' },
  { key: 'pm',         label: 'PM',          type: 'text' },
  { key: 'customer',   label: 'Customer',    type: 'text' },
  { key: 'value',      label: 'Value',       type: 'number' },
  { key: 'priority',   label: 'Priority',    type: 'text' },
  { key: 'status',     label: 'Status',      type: 'text' },
  { key: 'progress',   label: 'Progress %',  type: 'number' },
  { key: 'fiscalYear', label: 'Fiscal year', type: 'text' },
  { key: 'startDate',  label: 'Start date',  type: 'date' },
  { key: 'dueDate',    label: 'Due date',    type: 'date' },
]

function projectRow(p) {
  return {
    domain: p.domain || '',
    name: p.name || '',
    code: p.code || '',
    pm: p.pm || (p.pms?.length ? p.pms.map((u) => u.name).join(' / ') : ''),
    customer: p.customer || '',
    value: p.value == null ? null : Number(p.value),
    priority: p.priority || '',
    status: p.status || '',
    progress: taskProgress(p),
    fiscalYear: p.fiscalYear || '',
    startDate: p.startDate || '',
    dueDate: p.dueDate || '',
  }
}

export async function exportProjectsExcel(projects, filename) {
  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet('Projects')
  ws.columns = PROJECT_COLUMNS.map((c) => ({ header: c.label, key: c.key, width: 16 }))

  for (const p of projects) {
    const row = projectRow(p)
    const cells = {}
    for (const c of PROJECT_COLUMNS) {
      const v = row[c.key]
      if (c.type === 'date') cells[c.key] = isoToExcelDate(v)
      else if (c.type === 'number') cells[c.key] = v == null || v === '' ? null : Number(v)
      else cells[c.key] = v ?? ''
    }
    ws.addRow(cells)
  }

  PROJECT_COLUMNS.forEach((c, i) => {
    const col = ws.getColumn(i + 1)
    if (c.type === 'date') col.numFmt = 'dd/mm/yyyy'
    else if (c.type === 'number') col.numFmt = '#,##0'
  })

  const header = ws.getRow(1)
  header.font = { bold: true, color: { argb: 'FFFFFFFF' } }
  header.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }
  header.alignment = { vertical: 'middle' }
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: PROJECT_COLUMNS.length } }
  ws.views = [{ state: 'frozen', ySplit: 1 }]

  ws.columns.forEach((column) => {
    let max = 0
    column.eachCell({ includeEmpty: true }, (cell) => {
      const len = cell.value == null ? 0 : String(cell.value).length
      if (len > max) max = len
    })
    column.width = Math.min(Math.max(max + 4, 12), 60)
  })

  const name = filename || `projects-${stamp()}.xlsx`
  await writeAndDownload(wb, name)
}

export function exportProjectsPdf(projects, filename) {
  const doc = new jsPDF({ orientation: 'landscape', format: 'a4' })
  const font = registerThaiFont(doc)
  const title = 'Projects'
  const printed = new Date().toLocaleString('en-GB')
  const head = [PROJECT_COLUMNS.map((c) => c.label)]
  const body = projects.map((p) => {
    const row = projectRow(p)
    return PROJECT_COLUMNS.map((c) => {
      const v = row[c.key]
      if (c.type === 'date') return v ? formatDate(v) : '—'
      if (c.type === 'number') return v == null || v === '' ? '—' : Number(v).toLocaleString()
      return v == null || v === '' ? '—' : String(v)
    })
  })

  autoTable(doc, {
    head,
    body,
    startY: 56,
    margin: { top: 56, bottom: 28, left: 20, right: 20 },
    styles: { font, fontStyle: 'normal', fontSize: 8, overflow: 'linebreak', cellPadding: 3 },
    headStyles: { font, fillColor: [79, 129, 189], textColor: 255, fontSize: 8 },
    didDrawPage: () => {
      doc.setFont(font)
      doc.setFontSize(13)
      doc.text(title, 20, 34)
      doc.setFontSize(8)
      doc.text(`Generated ${printed}`, 20, 46)
    },
  })

  const total = doc.internal.getNumberOfPages()
  const w = doc.internal.pageSize.getWidth()
  const h = doc.internal.pageSize.getHeight()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setFont(font)
    doc.setFontSize(8)
    doc.text(`Page ${i} of ${total}`, w - 20, h - 14, { align: 'right' })
  }
  doc.save(filename || `projects-${stamp()}.pdf`)
}

export function exportProjectsCsv(projects, filename) {
  const headers = PROJECT_COLUMNS.map((c) => c.label)
  const lines = projects.map((p) => {
    const row = projectRow(p)
    return PROJECT_COLUMNS.map((c) => {
      const v = row[c.key]
      const s = v == null ? '' : String(v)
      return `"${s.replace(/"/g, '""')}"`
    }).join(',')
  })
  const blob = new Blob(['\uFEFF' + headers.join(',') + '\n' + lines.join('\n')], {
    type: 'text/csv;charset=utf-8',
  })
  triggerDownload(blob, filename || `projects-${stamp()}.csv`)
}

// ---------------------------------------------------------------------------
// Global BOM inventory exports (BomGlobalView.vue)
// Like the project-list exports, this is a column-driven path: the generic
// exportRecords*('bom', …) omits the cross-project context, so we prepend a
// "Project" column to the BOM schema fields. Rows carry `projectName` from the
// /bom/all endpoint plus the standard bom record keys.
// ---------------------------------------------------------------------------
const BOM_INVENTORY_COLUMNS = [
  { key: 'projectName', label: 'Project', type: 'text' },
  ...RECORD_SCHEMAS.bom.fields.map((f) => ({ key: f.key, label: f.label, type: f.type })),
]

export async function exportBomInventoryExcel(rows, filename) {
  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet('BOM')
  ws.columns = BOM_INVENTORY_COLUMNS.map((c) => ({ header: c.label, key: c.key, width: 16 }))

  for (const row of rows) {
    const cells = {}
    for (const c of BOM_INVENTORY_COLUMNS) {
      const v = row[c.key]
      if (c.type === 'date') cells[c.key] = isoToExcelDate(v)
      else if (c.type === 'number') cells[c.key] = v == null || v === '' ? null : Number(v)
      else cells[c.key] = v ?? ''
    }
    ws.addRow(cells)
  }

  BOM_INVENTORY_COLUMNS.forEach((c, i) => {
    const col = ws.getColumn(i + 1)
    if (c.type === 'date') col.numFmt = 'dd/mm/yyyy'
    else if (c.type === 'number') col.numFmt = '#,##0'
  })

  const header = ws.getRow(1)
  header.font = { bold: true, color: { argb: 'FFFFFFFF' } }
  header.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }
  header.alignment = { vertical: 'middle' }
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: BOM_INVENTORY_COLUMNS.length } }
  ws.views = [{ state: 'frozen', ySplit: 1 }]

  ws.columns.forEach((column) => {
    let max = 0
    column.eachCell({ includeEmpty: true }, (cell) => {
      const len = cell.value == null ? 0 : String(cell.value).length
      if (len > max) max = len
    })
    column.width = Math.min(Math.max(max + 4, 12), 60)
  })

  await writeAndDownload(wb, filename || `bom-inventory-${stamp()}.xlsx`)
}

export function exportBomInventoryPdf(rows, filename) {
  const doc = new jsPDF({ orientation: 'landscape', format: 'a4' })
  const font = registerThaiFont(doc)
  const title = 'BOM Inventory'
  const printed = new Date().toLocaleString('en-GB')
  const head = [BOM_INVENTORY_COLUMNS.map((c) => c.label)]
  const body = rows.map((row) =>
    BOM_INVENTORY_COLUMNS.map((c) => displayValue(c, row[c.key])),
  )

  autoTable(doc, {
    head,
    body,
    startY: 56,
    margin: { top: 56, bottom: 28, left: 20, right: 20 },
    styles: { font, fontStyle: 'normal', fontSize: 8, overflow: 'linebreak', cellPadding: 3 },
    headStyles: { font, fillColor: [79, 129, 189], textColor: 255, fontSize: 8 },
    didDrawPage: () => {
      doc.setFont(font)
      doc.setFontSize(13)
      doc.text(title, 20, 34)
      doc.setFontSize(8)
      doc.text(`Generated ${printed}`, 20, 46)
    },
  })

  const total = doc.internal.getNumberOfPages()
  const w = doc.internal.pageSize.getWidth()
  const h = doc.internal.pageSize.getHeight()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setFont(font)
    doc.setFontSize(8)
    doc.text(`Page ${i} of ${total}`, w - 20, h - 14, { align: 'right' })
  }
  doc.save(filename || `bom-inventory-${stamp()}.pdf`)
}

// ---------------------------------------------------------------------------
// Excel import
// ---------------------------------------------------------------------------

// Neutralize CSV/formula-injection by quoting cells that begin with = + - @.
function sanitizeText(s) {
  const t = String(s)
  return /^[=+\-@]/.test(t) ? `'${t}` : t
}

function cellToString(value) {
  if (value == null) return ''
  if (typeof value === 'object') {
    if (value instanceof Date) return value.toISOString()
    if ('text' in value) return String(value.text) // rich text / hyperlink
    if ('result' in value) return String(value.result) // formula
    if ('richText' in value) return value.richText.map((r) => r.text).join('')
  }
  return String(value)
}

// Build a YYYY-MM-DD string only if y/m/d form a real calendar date.
function buildDate(y, mo, d) {
  const dt = new Date(y, mo - 1, d)
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function normalizeDate(value) {
  // ExcelJS hands back Date objects at UTC midnight; read with UTC getters so
  // negative-offset zones don't shift the calendar day back by one.
  if (value instanceof Date && !isNaN(value)) {
    return buildDate(value.getUTCFullYear(), value.getUTCMonth() + 1, value.getUTCDate())
  }
  const s = cellToString(value).trim()
  if (!s) return ''
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s)
  if (m) return buildDate(+m[1], +m[2], +m[3])
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s) // DD/MM/YYYY
  if (m) return buildDate(+m[3], +m[2], +m[1])
  const d = new Date(s)
  if (!isNaN(d)) return buildDate(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate())
  return null // unparseable
}

function validateFileBasics(file) {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!['.xlsx', '.xls'].includes(ext)) {
    throw new Error('Invalid file type. Please upload an .xlsx or .xls file.')
  }
  if (file.size > MAX_IMPORT_BYTES) {
    throw new Error('File too large. Maximum size is 10MB.')
  }
}

// Parse a single worksheet against one resource's schema. Returns
// { valid, errors, unmatched }. Shared by single + multi-resource importers.
function parseWorksheet(ws, resource) {
  const fields = fieldsFor(resource)

  const byHeader = new Map()
  for (const f of fields) {
    byHeader.set(f.label.trim().toLowerCase(), f.key)
    byHeader.set(f.key.trim().toLowerCase(), f.key)
  }
  const fieldByType = Object.fromEntries(fields.map((f) => [f.key, f]))

  const colToField = {}
  const unmatched = []
  const headerRow = ws.getRow(1)
  headerRow.eachCell((cell, col) => {
    const raw = cellToString(cell.value).trim()
    if (!raw) return
    const key = byHeader.get(raw.toLowerCase())
    if (key) colToField[col] = key
    else unmatched.push(raw)
  })

  if (!Object.keys(colToField).length) {
    return {
      valid: [],
      errors: [{ row: 1, column: '(header)', message: 'No recognizable columns found.' }],
      unmatched,
    }
  }

  const valid = []
  const errors = []

  for (let r = 2; r <= ws.rowCount; r++) {
    const xlRow = ws.getRow(r)
    const record = {}
    let hasValue = false
    let rowHadError = false

    for (const [colStr, key] of Object.entries(colToField)) {
      const field = fieldByType[key]
      const raw = xlRow.getCell(Number(colStr)).value
      const str = cellToString(raw).trim()

      if (field.type === 'number') {
        if (str === '') {
          record[key] = null
        } else {
          const n = Number(str.replace(/,/g, ''))
          if (Number.isNaN(n)) {
            errors.push({ row: r, column: field.label, message: `"${str}" is not a number` })
            rowHadError = true
          } else {
            record[key] = n
            hasValue = true
          }
        }
      } else if (field.type === 'date') {
        if (str === '') {
          record[key] = ''
        } else {
          const norm = normalizeDate(raw)
          if (norm === null) {
            errors.push({ row: r, column: field.label, message: `"${str}" is not a valid date` })
            rowHadError = true
          } else {
            record[key] = norm
            hasValue = true
          }
        }
      } else if (field.type === 'checkbox') {
        record[key] = TRUTHY.has(str.toLowerCase())
      } else {
        record[key] = sanitizeText(str)
        if (str) hasValue = true
      }
    }

    if (!hasValue) continue
    if (!rowHadError) valid.push(record)
  }

  return { valid, errors, unmatched }
}

/**
 * Parse an uploaded Excel file into records for one resource.
 * @returns {Promise<{valid: object[], errors: {row:number,column:string,message:string}[], unmatched: string[]}>}
 */
export async function parseRecordsExcel(resource, file) {
  validateFileBasics(file)
  const wb = new ExcelJS.Workbook()
  await wb.xlsx.load(await file.arrayBuffer())
  const ws = wb.worksheets[0]
  if (!ws) throw new Error('The workbook has no sheets.')

  const result = parseWorksheet(ws, resource)
  // Preserve the previous behavior: hard error when no header column matches.
  if (
    !result.valid.length &&
    result.errors.length === 1 &&
    result.errors[0].row === 1 &&
    result.errors[0].column === '(header)'
  ) {
    throw new Error('No recognizable columns found. Check that the header row matches the field names.')
  }
  return result
}

/**
 * Parse an uploaded Excel file as a global BOM inventory sheet. The header row
 * is expected to include a "Project" (or "Project name" / "Project id") column
 * in addition to the standard `bom` field columns. Project values are matched
 * case-insensitively against the provided projects list by name, or as an
 * integer against project IDs. Rows whose project can't be resolved are
 * reported as errors and excluded from `valid`.
 *
 * @param {File} file
 * @param {{id:number, name:string}[]} projects
 * @returns {Promise<{ valid: object[], errors: {row:number,column:string,message:string}[], unmatched: string[] }>}
 */
export async function parseBomInventoryExcel(file, projects) {
  validateFileBasics(file)
  const wb = new ExcelJS.Workbook()
  await wb.xlsx.load(await file.arrayBuffer())
  const ws = wb.worksheets[0]
  if (!ws) throw new Error('The workbook has no sheets.')

  const fields = fieldsFor('bom')
  const fieldByKey = Object.fromEntries(fields.map((f) => [f.key, f]))

  const PROJECT_ALIASES = new Set([
    'project', 'projectname', 'project name', 'projectid', 'project id',
  ])

  const byHeader = new Map()
  for (const f of fields) {
    byHeader.set(f.label.trim().toLowerCase(), { kind: 'field', key: f.key })
    byHeader.set(f.key.trim().toLowerCase(), { kind: 'field', key: f.key })
  }

  const nameToId = new Map()
  const idSet = new Set()
  for (const p of projects || []) {
    if (p.name) nameToId.set(String(p.name).trim().toLowerCase(), p.id)
    idSet.add(p.id)
  }

  const colMap = {}
  const unmatched = []
  ws.getRow(1).eachCell((cell, col) => {
    const raw = cellToString(cell.value).trim()
    if (!raw) return
    const lc = raw.toLowerCase()
    if (PROJECT_ALIASES.has(lc)) { colMap[col] = { kind: 'project' }; return }
    const m = byHeader.get(lc)
    if (m) colMap[col] = m
    else unmatched.push(raw)
  })

  const hasFieldCol = Object.values(colMap).some((m) => m.kind === 'field')
  if (!hasFieldCol) {
    throw new Error('No recognizable columns found. Check that the header row matches the field names.')
  }

  const valid = []
  const errors = []

  for (let r = 2; r <= ws.rowCount; r++) {
    const xlRow = ws.getRow(r)
    const record = {}
    let projectId = null
    let projectRaw = ''
    let hasValue = false
    let rowHadError = false

    for (const [colStr, m] of Object.entries(colMap)) {
      const col = Number(colStr)
      const raw = xlRow.getCell(col).value
      const str = cellToString(raw).trim()

      if (m.kind === 'project') {
        projectRaw = str
        if (!str) continue
        const n = Number(str)
        if (Number.isInteger(n) && idSet.has(n)) projectId = n
        else if (nameToId.has(str.toLowerCase())) projectId = nameToId.get(str.toLowerCase())
        continue
      }

      const field = fieldByKey[m.key]
      if (field.type === 'number') {
        if (str === '') {
          record[field.key] = null
        } else {
          const n = Number(str.replace(/,/g, ''))
          if (Number.isNaN(n)) {
            errors.push({ row: r, column: field.label, message: `"${str}" is not a number` })
            rowHadError = true
          } else {
            record[field.key] = n
            hasValue = true
          }
        }
      } else if (field.type === 'date') {
        if (str === '') {
          record[field.key] = ''
        } else {
          const norm = normalizeDate(raw)
          if (norm === null) {
            errors.push({ row: r, column: field.label, message: `"${str}" is not a valid date` })
            rowHadError = true
          } else {
            record[field.key] = norm
            hasValue = true
          }
        }
      } else if (field.type === 'checkbox') {
        record[field.key] = TRUTHY.has(str.toLowerCase())
      } else {
        record[field.key] = sanitizeText(str)
        if (str) hasValue = true
      }
    }

    if (!hasValue && !projectId && !projectRaw) continue
    if (!projectId) {
      errors.push({
        row: r,
        column: 'Project',
        message: projectRaw ? `Unknown project "${projectRaw}"` : 'Project is required',
      })
      rowHadError = true
    }
    if (!rowHadError) valid.push({ ...record, projectId })
  }

  return { valid, errors, unmatched }
}

/**
 * Parse an uploaded Excel file as a multi-resource workbook. Each worksheet is
 * matched (case-insensitive) against the supplied resource list by either the
 * schema label or the resource key. Unmatched sheets are reported separately.
 *
 * @param {string[]} resources - e.g. ['survey','mom','verification','exceptions']
 * @param {File} file
 * @returns {Promise<{ perResource: Record<string, {valid, errors, unmatched}>, unknownSheets: string[] }>}
 */
export async function parseRecordsExcelMulti(resources, file) {
  validateFileBasics(file)
  const wb = new ExcelJS.Workbook()
  await wb.xlsx.load(await file.arrayBuffer())
  if (!wb.worksheets.length) throw new Error('The workbook has no sheets.')

  const aliases = new Map()
  for (const r of resources) {
    const schema = RECORD_SCHEMAS[r]
    if (!schema) continue
    aliases.set(r, [schema.label.trim().toLowerCase(), r.toLowerCase()])
  }

  const perResource = {}
  const unknownSheets = []

  for (const ws of wb.worksheets) {
    const name = (ws.name || '').trim().toLowerCase()
    if (!name) continue
    let matched = null
    for (const [resource, [label, key]] of aliases) {
      if (name === label || name === key || name.startsWith(label) || name.startsWith(key)) {
        matched = resource
        break
      }
    }
    if (!matched) {
      unknownSheets.push(ws.name)
      continue
    }
    const prev = perResource[matched]
    const current = parseWorksheet(ws, matched)
    if (prev) {
      perResource[matched] = {
        valid: prev.valid.concat(current.valid),
        errors: prev.errors.concat(current.errors),
        unmatched: Array.from(new Set(prev.unmatched.concat(current.unmatched))),
      }
    } else {
      perResource[matched] = current
    }
  }

  return { perResource, unknownSheets }
}

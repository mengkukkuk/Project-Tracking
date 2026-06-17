import { computed } from 'vue'

// Shared ptrack date-chain + status derivation.
// Lifted from components/ProcessChecklist.vue so DashboardView (Sections 1 & 4)
// and the drawer checklist agree on health/blocker/per-row status.
//
// chain:
//   first process:  start = projectStart,    due = start + dayRange
//   subsequent:     start = prevDue + 1 day, due = start + dayRange

function addDays(iso, days) {
  if (!iso || days == null) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  d.setDate(d.getDate() + Number(days))
  return d.toISOString().slice(0, 10)
}

function daysUntilLocal(iso) {
  if (!iso) return null
  const d = new Date(iso); d.setHours(0, 0, 0, 0)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.floor((d.getTime() - today.getTime()) / 86400000)
}

export function useProcessChain(rowsRef, startDateRef) {
  const groups = computed(() => {
    const rows = rowsRef.value || []
    if (!rows.length) return []
    const map = new Map()
    for (const r of rows) {
      const key = r.process || 'Ungrouped'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(r)
    }
    const projectStart = startDateRef.value || null
    const list = [...map.entries()].map(([process, items]) => {
      const sample = items.find((i) => i.cumulativeDays != null) || items[0] || {}
      return {
        process,
        items,
        done: items.filter((i) => i.checked).length,
        dayRange: sample.dayRange ?? null,
        cumulativeDays: sample.cumulativeDays ?? null,
      }
    })
    list.sort((a, b) => {
      if (a.cumulativeDays == null) return 1
      if (b.cumulativeDays == null) return -1
      return a.cumulativeDays - b.cumulativeDays
    })
    let prevDue = null
    for (const g of list) {
      g.startDate = prevDue ? addDays(prevDue, 1) : projectStart
      g.dueDate = addDays(g.startDate, g.dayRange)
      g.remaining = daysUntilLocal(g.dueDate)
      if (g.dueDate) prevDue = g.dueDate
    }
    const today = new Date(); today.setHours(0, 0, 0, 0)
    for (const g of list) {
      for (const r of g.items) {
        if (r.checked) { r._status = 'Done'; continue }
        if (!g.startDate) { r._status = 'Not started'; continue }
        const s = new Date(g.startDate); s.setHours(0, 0, 0, 0)
        r._status = s.getTime() > today.getTime() ? 'Not started' : 'In progress'
      }
    }
    return list
  })

  // First still-incomplete group in cumulativeDays order; matches the
  // template's "1. Site Survey & Draft (Service Team)" example.
  const blocker = computed(() => {
    for (const g of groups.value) {
      if (g.done < g.items.length) {
        const row = g.items.find((i) => !i.checked) || g.items[0]
        const resp = row?.pm || ''
        return {
          process: g.process,
          responsible: resp,
          label: resp ? `${g.process} (${resp})` : g.process,
        }
      }
    }
    return null
  })

  // Health considers only still-incomplete groups; a fully-done group can't
  // block the project even if its date math is in the past.
  const health = computed(() => {
    const list = groups.value
    if (!list.length) return { key: 'unknown', label: 'No data', emoji: '⚪' }
    let anyOverdue = false
    let anySoon = false
    for (const g of list) {
      if (g.done >= g.items.length) continue
      if (g.remaining == null) continue
      if (g.remaining < 0) anyOverdue = true
      else if (g.remaining <= 7) anySoon = true
    }
    if (anyOverdue) return { key: 'risk', label: 'At Risk', emoji: '🔴' }
    if (anySoon) return { key: 'watch', label: 'Watch', emoji: '🟡' }
    return { key: 'ontrack', label: 'On Track', emoji: '🟢' }
  })

  return { groups, blocker, health }
}

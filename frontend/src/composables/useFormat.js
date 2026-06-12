// Shared formatters used across all views.
export function useFormat() {
  const baht = (v) => {
    if (v == null) return '-'
    if (v >= 1e9) return `฿${(v / 1e9).toFixed(1)}B`
    if (v >= 1e6) return `฿${(v / 1e6).toFixed(v % 1e6 === 0 ? 0 : 1)}M`
    if (v >= 1e3) return `฿${(v / 1e3).toFixed(0)}K`
    return `฿${v}`
  }

  const fy = (y) => (y === 'future' || !y ? 'ในอนาคต' : `ปีงบ ${y}`)

  const date = (iso) => {
    if (!iso) return '-'
    const d = new Date(iso)
    return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: '2-digit' })
  }

  const relative = (iso) => {
    if (!iso) return ''
    const diff = (Date.now() - new Date(iso).getTime()) / 1000
    const abs = Math.abs(diff)
    const units = [
      [60, 'วินาที'],
      [3600, 'นาที', 60],
      [86400, 'ชั่วโมง', 3600],
      [2592000, 'วัน', 86400],
    ]
    for (const [limit, label, div] of units) {
      if (abs < limit) {
        const n = div ? Math.floor(abs / div) : Math.floor(abs)
        return diff >= 0 ? `${n} ${label}ที่แล้ว` : `อีก ${n} ${label}`
      }
    }
    return date(iso)
  }

  // Days until a due date; negative means overdue.
  const daysUntil = (iso) => {
    if (!iso) return null
    const d = new Date(iso)
    d.setHours(0, 0, 0, 0)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return Math.round((d - today) / 86400000)
  }

  return { baht, fy, date, relative, daysUntil }
}

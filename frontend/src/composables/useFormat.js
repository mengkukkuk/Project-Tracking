// Shared formatters used across all views.
export function useFormat() {
  const baht = (v) => {
    const value = Number(v || 0)
    if (v == null) return '-'
    if (value >= 1e9) return `฿${(value / 1e9).toFixed(1)}B`
    if (value >= 1e6) return `฿${(value / 1e6).toFixed(value % 1e6 === 0 ? 0 : 1)}M`
    if (value >= 1e3) return `฿${(value / 1e3).toFixed(0)}K`
    return `฿${value}`
  }

  const fy = (y) => (y === 'future' || !y ? 'Future' : `FY${y}`)

  const date = (iso) => {
    if (!iso) return '-'
    const d = new Date(iso)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })
  }

  const relative = (iso) => {
    if (!iso) return ''
    const diff = (Date.now() - new Date(iso).getTime()) / 1000
    const abs = Math.abs(diff)
    const units = [
      [60, 'second'],
      [3600, 'minute', 60],
      [86400, 'hour', 3600],
      [2592000, 'day', 86400],
    ]
    for (const [limit, label, div] of units) {
      if (abs < limit) {
        const n = div ? Math.floor(abs / div) : Math.floor(abs)
        const word = `${label}${n === 1 ? '' : 's'}`
        return diff >= 0 ? `${n} ${word} ago` : `in ${n} ${word}`
      }
    }
    return date(iso)
  }

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

// Summaries page: 4-step pipeline math (inputs -> calculated metrics -> final results).
// Pure functions only — no store/API access — so the view can recompute on every keystroke.

export const PRIORITY_COMPLEXITY = { low: 3, medium: 5, high: 7, critical: 9 }

export const SUMMARY_COLORS = {
  roi: '#6366f1',
  health: '#10b981',
  performance: '#f59e0b',
  safety: '#ec4899',
}

export const GRADE_COLORS = {
  A: '#10b981',
  B: '#3b82f6',
  C: '#f59e0b',
  D: '#ef4444',
}

export function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n))
}

// team_size is unset until the user (or ProjectForm) sets it explicitly —
// seed a reasonable default from the number of assigned PMs.
export function seedTeamSize(p) {
  if (p?.teamSize != null) return p.teamSize
  return Math.max(1, p?.pms?.length || 1)
}

// complexity is unset until explicitly set — seed from priority.
export function seedComplexity(p) {
  if (p?.complexity != null) return p.complexity
  return PRIORITY_COMPLEXITY[p?.priority] || PRIORITY_COMPLEXITY.medium
}

// Duration is a what-if input derived from the project's date range — never
// persisted, since rewriting dueDate would trigger the server's process
// checklist date recompute and shift overdue flags elsewhere in the app.
export function derivedDurationWeeks(p) {
  if (!p?.startDate || !p?.dueDate) return 12
  const start = new Date(p.startDate)
  const due = new Date(p.dueDate)
  const days = (due - start) / 86400000
  return Math.max(1, Math.round(days / 7))
}

export function computeMetrics(inputs) {
  const budget = Math.max(0, Number(inputs.budget) || 0)
  const teamSize = Math.max(1, Number(inputs.teamSize) || 1)
  const durationWeeks = Math.max(1, Number(inputs.durationWeeks) || 1)
  const complexity = Math.max(1, Number(inputs.complexity) || 1)
  return {
    costPerResource: budget / teamSize,
    weeklyBurnRate: budget / durationWeeks,
    productivityIndex: (teamSize * 10) / complexity,
    resourceEfficiency: budget / (teamSize * durationWeeks * 100),
  }
}

export function computeResults(metrics, inputs) {
  //Calculations
  const { productivityIndex, resourceEfficiency, weeklyBurnRate } = metrics
  const teamSize = Math.max(1, Number(inputs.teamSize) || 1)
  const complexity = Math.max(1, Number(inputs.complexity) || 1)
  const durationWeeks = Math.max(1, Number(inputs.durationWeeks) || 1)

  //Final results
  const roiScore = Math.min(100, (productivityIndex * 1000) / (resourceEfficiency + 1))
  const riskLevel = Math.min(100, (complexity * 12) / (teamSize / 5 + 1))
  const performanceRating = Math.min(100, (productivityIndex + roiScore) / 2)
  const healthScore = clamp(100 - riskLevel * 0.6 + (resourceEfficiency > 3 ? 12 : 0), 0, 100)
  const totalCost = weeklyBurnRate * durationWeeks
  const safety = 100 - riskLevel

  return { roiScore, riskLevel, performanceRating, healthScore, totalCost, safety }
}

export function gradeFor(performanceRating) {
  if (performanceRating >= 80) return 'A'
  if (performanceRating >= 65) return 'B'
  if (performanceRating >= 50) return 'C'
  return 'D'
}

// 5th radar axis: resourceEfficiency scaled onto the same 0-100 range as the
// other scores (matches the source design's radar chart).
export function efficiencyAxis(metrics) {
  return Math.min(100, metrics.resourceEfficiency * 20)
}

// One-shot pipeline for a project, with optional what-if overrides for the
// 4 editable inputs (budget/teamSize/durationWeeks/complexity).
export function summarize(p, overrides = {}) {
  const inputs = {
    budget: overrides.budget ?? p?.value ?? 0,
    teamSize: overrides.teamSize ?? seedTeamSize(p),
    durationWeeks: overrides.durationWeeks ?? derivedDurationWeeks(p),
    complexity: overrides.complexity ?? seedComplexity(p),
  }
  const metrics = computeMetrics(inputs)
  const results = computeResults(metrics, inputs)
  const grade = gradeFor(results.performanceRating)
  return { inputs, metrics, results, grade }
}

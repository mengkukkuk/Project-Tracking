// Side-nav page catalog — MUST stay in sync with backend PAGE_KEYS
// (backend/app/permissions.py) and the routes in router.js.
export const PAGES = [
  { key: 'overview', path: '/', label: 'Overview', icon: 'overview' },
  { key: 'pipeline', path: '/pipeline', label: 'Pipeline', icon: 'pipelines' },
  { key: 'table', path: '/table', label: 'Table', icon: 'table' },
  { key: 'bom', path: '/bom', label: 'BOM', icon: 'money' },
  { key: 'dashboard', path: '/dashboard', label: 'Dashboard', icon: 'target' },
  { key: 'summaries', path: '/summaries', label: 'Summaries', icon: 'calculator' },
]

export const pagePerm = (key) => `page.${key}`

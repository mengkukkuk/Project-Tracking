// Centralized API client.
// - Injects the JWT bearer token from localStorage.
// - Normalizes the backend's {error:{...}} envelope into thrown Error objects.
// - On 401 it clears the token and redirects to /login.
const BASE = import.meta.env.VITE_API_BASE || ''
const TOKEN_KEY = 'mml.token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

function buildError(status, body) {
  const e = body?.error
  let msg = `เกิดข้อผิดพลาด (${status})`
  if (e) {
    if (e.type === 'validation' && e.fields) {
      msg = Object.entries(e.fields)
        .map(([k, v]) => (k === '_' ? v : `${k}: ${v}`))
        .join(' · ')
    } else if (e.message) {
      msg = e.message
    }
  }
  const err = new Error(msg)
  err.status = status
  err.body = body
  return err
}

async function req(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`${BASE}/api${path}`, { ...opts, headers })
  } catch {
    throw new Error('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้')
  }

  if (res.status === 401 && !path.startsWith('/auth/')) {
    setToken(null)
    if (location.pathname !== '/login') location.assign('/login')
    throw buildError(401, await res.json().catch(() => null))
  }

  if (res.status === 204) return null
  const body = await res.json().catch(() => null)
  if (!res.ok) throw buildError(res.status, body)
  return body
}

const qs = (params) => {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== '' && v != null) s.append(k, v)
  }
  const str = s.toString()
  return str ? `?${str}` : ''
}

export const api = {
  // auth
  register: (d) => req('/auth/register', { method: 'POST', body: JSON.stringify(d) }),
  login: (d) => req('/auth/login', { method: 'POST', body: JSON.stringify(d) }),
  me: () => req('/auth/me'),

  // projects
  listProjects: (params) => req(`/projects${qs(params)}`),
  getProject: (id) => req(`/projects/${id}`),
  createProject: (d) => req('/projects', { method: 'POST', body: JSON.stringify(d) }),
  updateProject: (id, d) => req(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
  deleteProject: (id) => req(`/projects/${id}`, { method: 'DELETE' }),
  generatePtrack: (pid) => req(`/projects/${pid}/ptrack/generate`, { method: 'POST' }),

  // tasks
  createTask: (pid, d) => req(`/projects/${pid}/tasks`, { method: 'POST', body: JSON.stringify(d) }),
  updateTask: (id, d) => req(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
  deleteTask: (id) => req(`/tasks/${id}`, { method: 'DELETE' }),

  // comments
  createComment: (pid, d) => req(`/projects/${pid}/comments`, { method: 'POST', body: JSON.stringify(d) }),
  deleteComment: (id) => req(`/comments/${id}`, { method: 'DELETE' }),

  // per-project records (ptrack, survey, mom, bom, verification, exceptions)
  listRecords: (pid, resource) => req(`/projects/${pid}/records/${resource}`),
  // global BOM list across all projects (each row enriched with projectName)
  listBomAll: () => req('/bom/all'),
  createRecord: (pid, resource, d) =>
    req(`/projects/${pid}/records/${resource}`, { method: 'POST', body: JSON.stringify(d) }),
  updateRecord: (resource, id, d) =>
    req(`/records/${resource}/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
  deleteRecord: (resource, id) =>
    req(`/records/${resource}/${id}`, { method: 'DELETE' }),

  // misc
  stats: () => req('/stats'),
  listUsers: () => req('/users'),

  // google sheets
  sheetsStatus: () => req('/sheets/status'),
  sheetsExport: () => req('/sheets/export', { method: 'POST' }),
  sheetsImport: (preview = false) =>
    req(`/sheets/import${preview ? '?preview=1' : ''}`, { method: 'POST' }),
}

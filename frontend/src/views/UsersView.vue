<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { PAGES } from '@/constants/pages'

const auth = useAuthStore()
const ui = useUiStore()

const users = ref([])
const loading = ref(true)
const savingId = ref(null)

// Assignable roles, most-privileged first. An admin may not grant super_admin —
// the backend rejects it, and we also hide the option to match (UI is advisory).
const ALL_ROLES = ['super_admin', 'admin', 'member']
const assignableRoles = computed(() =>
  auth.isSuperAdmin ? ALL_ROLES : ALL_ROLES.filter((r) => r !== 'super_admin'),
)

// Page-access checkboxes: members only — super_admin/admin always have every
// page, so the column only offers editing for member rows. Backend re-derives
// and enforces on every request; this is UX only.
const ELEVATED_ROLES = ['super_admin', 'admin']
const canEditPages = computed(() => auth.hasPermission('pages.assign'))

async function togglePage(u, key, event) {
  const next = new Set(u.pageAccess)
  if (next.has(key)) {
    if (next.size === 1) {
      // Bail without touching u.pageAccess, so the checkbox is left as an
      // uncontrolled input the browser already toggled — force it back or
      // it stays visually unchecked even though nothing was saved.
      event.target.checked = true
      ui.error('At least one page must remain accessible')
      return
    }
    next.delete(key)
  } else {
    next.add(key)
  }
  const prev = u.pageAccess
  u.pageAccess = PAGES.map((p) => p.key).filter((k) => next.has(k)) // optimistic
  savingId.value = u.id
  try {
    const updated = await api.setUserPages(u.id, u.pageAccess)
    Object.assign(u, updated)
  } catch (e) {
    u.pageAccess = prev // rollback
    ui.error(e.message)
  } finally {
    savingId.value = null
  }
}

function canEdit(u) {
  // Cannot change your own role; only a super_admin may touch a super_admin.
  if (u.id === auth.user?.id) return false
  if (u.role === 'super_admin' && !auth.isSuperAdmin) return false
  return true
}

async function load() {
  loading.value = true
  try {
    const { items } = await api.listUsers()
    users.value = items
  } catch (e) {
    ui.error(e.message)
  } finally {
    loading.value = false
  }
}

async function changeRole(u, role) {
  if (role === u.role) return
  const prev = u.role
  u.role = role // optimistic
  savingId.value = u.id
  try {
    const updated = await api.setUserRole(u.id, role)
    Object.assign(u, updated)
    ui.success(`${u.name} is now ${role.replace('_', ' ')}`)
  } catch (e) {
    u.role = prev // rollback
    ui.error(e.message)
  } finally {
    savingId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="view">
    <header class="page-header">
      <div>
        <div class="page-kicker">Access control</div>
        <h1 class="page-title">Users &amp; Roles</h1>
        <p class="page-subtitle">กำหนดสิทธิ์การเข้าถึงของผู้ใช้แต่ละคน</p>
      </div>
    </header>

    <div v-if="loading" class="state">Loading users...</div>

    <div v-else class="card">
      <table class="users-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th class="role-col">Role</th>
            <th v-if="canEditPages" class="pages-col">Page access</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>
              <span class="avatar">{{ (u.name || '?').slice(0, 2).toUpperCase() }}</span>
              <span class="uname">{{ u.name }}</span>
              <span v-if="u.id === auth.user?.id" class="you">you</span>
            </td>
            <td class="email">{{ u.email }}</td>
            <td class="role-col">
              <select
                v-if="canEdit(u)"
                :value="u.role"
                :disabled="savingId === u.id"
                @change="changeRole(u, $event.target.value)"
              >
                <option v-for="r in assignableRoles" :key="r" :value="r">
                  {{ r.replace('_', ' ') }}
                </option>
              </select>
              <span v-else class="role-badge" :class="u.role">{{ u.role.replace('_', ' ') }}</span>
            </td>
            <td v-if="canEditPages" class="pages-col">
              <span v-if="ELEVATED_ROLES.includes(u.role)" class="role-badge">All pages</span>
              <div v-else class="page-checks">
                <label v-for="p in PAGES" :key="p.key" class="page-check">
                  <input
                    type="checkbox"
                    :checked="u.pageAccess.includes(p.key)"
                    :disabled="savingId === u.id"
                    @change="togglePage(u, p.key, $event)"
                  />
                  {{ p.label }}
                </label>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.state { padding: 48px; text-align: center; color: var(--text-dim); }
.users-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.users-table th {
  text-align: left; padding: 12px 16px; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em; color: var(--text-dim);
  border-bottom: 1px solid var(--border); background: var(--surface-2, transparent);
}
.users-table td {
  padding: 12px 16px; border-bottom: 1px solid var(--border); color: var(--text);
  vertical-align: middle;
}
.users-table tr:last-child td { border-bottom: 0; }
.avatar {
  display: inline-grid; place-items: center; width: 28px; height: 28px;
  border-radius: 50%; background: var(--accent); color: #fff; font-size: 11px;
  font-weight: 700; margin-right: 9px; vertical-align: middle;
}
.uname { font-weight: 600; }
.you {
  margin-left: 8px; font-size: 10px; font-weight: 700; text-transform: uppercase;
  color: var(--accent); border: 1px solid var(--accent); border-radius: 5px; padding: 1px 5px;
}
.email { color: var(--text-dim); }
.role-col { width: 180px; }
.role-col select {
  width: 100%; padding: 7px 9px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); color: var(--text); font-family: inherit; font-size: 13px;
  text-transform: capitalize; cursor: pointer;
}
.role-col select:disabled { opacity: .5; cursor: wait; }
.role-badge {
  display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px;
  font-weight: 700; text-transform: capitalize; background: var(--sidebar-hover, #eef2f7);
  color: var(--text-dim);
}
.role-badge.super_admin { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
.pages-col { min-width: 240px; }
.page-checks { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.page-check {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
  color: var(--text); cursor: pointer; white-space: nowrap;
}
.page-check input { accent-color: var(--accent); cursor: pointer; }
.page-check input:disabled { cursor: wait; }
</style>
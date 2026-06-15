<script setup>
import { ref, computed, watch } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Toasts from '@/components/Toasts.vue'
import Modal from '@/components/Modal.vue'
import ProjectForm from '@/components/ProjectForm.vue'
import ProjectDetail from '@/components/ProjectDetail.vue'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const store = useProjectsStore()
const auth = useAuthStore()
const ui = useUiStore()

const nav = [
  { to: '/', label: 'Overview', icon: 'overview' },
  { to: '/pipeline', label: 'Pipeline', icon: 'pipeline' },
  { to: '/table', label: 'Table', icon: 'table' },
]

const isPublic = computed(() => route.meta.public)

// form modal: undefined = closed, null = create, object = edit
const formProject = ref(undefined)
const submitting = ref(false)

function openCreate() { formProject.value = null }
function openEdit(p) { store.closeDetail(); formProject.value = p }

async function handleSubmit(data) {
  submitting.value = true
  try {
    if (formProject.value) await store.updateProject(formProject.value.id, data)
    else await store.createProject(data)
    formProject.value = undefined
  } catch (e) {
    ui.error(e.message)
  } finally {
    submitting.value = false
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

watch(
  () => [auth.isAuthed, isPublic.value],
  ([authed, pub]) => {
    if (authed && !pub && !store.projects.length) store.fetchAll()
  },
  { immediate: true }
)
</script>

<template>
  <template v-if="isPublic">
    <RouterView />
    <Toasts />
  </template>

  <div v-else class="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo mono">PTrk</div>
        <div class="brand-text">
          <div class="brand-name">Project Tracking</div>
          <div class="brand-sub">Engineering Off-Site</div>
        </div>
      </div>

      <button class="new-btn btn" @click="openCreate">
        <AppIcon name="plus" :size="16" />
        New project
      </button>

      <nav aria-label="Main navigation">
        <RouterLink v-for="n in nav" :key="n.to" :to="n.to" class="nav-item">
          <AppIcon class="nav-icon" :name="n.icon" :size="17" />
          <span>{{ n.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <button class="theme-btn" @click="ui.toggleTheme">
          <AppIcon :name="ui.isDark ? 'sun' : 'moon'" :size="15" />
          {{ ui.isDark ? 'Light mode' : 'Dark mode' }}
        </button>
        <div class="user">
          <span class="avatar">{{ auth.initials }}</span>
          <div class="user-info">
            <div class="user-name">{{ auth.user?.name }}</div>
            <div class="user-role">{{ auth.user?.role }}</div>
          </div>
          <button class="logout" title="Sign out" @click="logout">
            <AppIcon name="logout" :size="16" />
          </button>
        </div>
      </div>
    </aside>

    <header class="topbar" aria-label="Mobile header">
      <div class="topbar-brand">
        <div class="logo mono">PTrk</div>
        <div>
          <div class="brand-name">Project Tracking</div>
          <div class="brand-sub">Engineering Off-Site</div>
        </div>
      </div>
      <div class="topbar-actions">
        <button class="ic-btn" @click="ui.toggleTheme" :aria-label="ui.isDark ? 'Light mode' : 'Dark mode'">
          <AppIcon :name="ui.isDark ? 'sun' : 'moon'" :size="16" />
        </button>
        <span class="avatar-sm" :title="auth.user?.name">{{ auth.initials }}</span>
        <button class="ic-btn" @click="logout" aria-label="Sign out">
          <AppIcon name="logout" :size="16" />
        </button>
      </div>
    </header>

    <main class="main">
      <div v-if="store.loading && !store.projects.length" class="state">Loading projects...</div>
      <div v-else-if="store.error" class="state err">
        {{ store.error }}
        <button class="btn ghost sm" @click="store.fetchAll">Try again</button>
      </div>
      <RouterView v-else />
    </main>

    <nav class="tabbar" aria-label="Mobile navigation">
      <RouterLink v-for="n in nav" :key="n.to" :to="n.to" class="tab-item">
        <AppIcon :name="n.icon" :size="18" />
        <span>{{ n.label }}</span>
      </RouterLink>
      <button class="tab-fab" @click="openCreate" aria-label="New project">
        <AppIcon name="plus" :size="20" />
      </button>
    </nav>

    <Modal
      v-if="formProject !== undefined"
      :title="formProject ? 'Edit project' : 'Create project'"
      wide
      @close="formProject = undefined"
    >
      <ProjectForm
        :project="formProject"
        :submitting="submitting"
        @submit="handleSubmit"
        @cancel="formProject = undefined"
      />
    </Modal>

    <ProjectDetail
      v-if="store.current || store.detailLoading"
      @close="store.closeDetail"
      @edit="openEdit"
    />

    <Toasts />
  </div>
</template>

<style scoped>
.app { display: flex; min-height: 100vh; }
.sidebar {
  width: 248px; flex-shrink: 0; background: var(--sidebar);
  display: flex; flex-direction: column; padding: 20px 14px; position: sticky; top: 0; height: 100vh;
}
.brand { display: flex; align-items: center; gap: 11px; padding: 0 6px 20px; }
.logo {
  width: 38px; height: 38px; border-radius: 8px; background: var(--accent); color: #fff;
  font-weight: 700; font-size: 13px; display: grid; place-items: center;
}
.brand-name { font-size: 14px; font-weight: 700; color: var(--sidebar-text); }
.brand-sub { font-size: 10px; color: var(--sidebar-dim); margin-top: 1px; white-space: nowrap; }
.new-btn { width: 100%; margin-bottom: 16px; }
nav { display: flex; flex-direction: column; gap: 3px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 11px; padding: 10px 13px; border-radius: 8px;
  font-size: 13px; color: var(--sidebar-dim); text-decoration: none; transition: background .12s, color .12s;
}
.nav-item:hover { background: var(--sidebar-hover); color: var(--sidebar-text); }
.nav-item.router-link-exact-active { background: var(--accent); color: #fff; font-weight: 700; }
.nav-icon { width: 17px; }
.sidebar-foot { display: flex; flex-direction: column; gap: 12px; }
.theme-btn {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  padding: 9px; border: 1px solid var(--sidebar-hover); background: transparent;
  color: var(--sidebar-dim); border-radius: 8px; font-size: 12px; cursor: pointer; font-family: inherit;
}
.theme-btn:hover { color: var(--sidebar-text); }
.user { display: flex; align-items: center; gap: 9px; padding: 8px; border-radius: 8px; background: var(--sidebar-hover); }
.avatar { width: 30px; height: 30px; border-radius: 50%; background: var(--accent); color: #fff; font-size: 11px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0; }
.user-info { flex: 1; min-width: 0; }
.user-name { font-size: 12px; font-weight: 700; color: var(--sidebar-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-role { font-size: 10px; color: var(--sidebar-dim); text-transform: uppercase; }
.logout { display: grid; place-items: center; background: none; border: none; color: var(--sidebar-dim); cursor: pointer; padding: 4px; }
.logout:hover { color: var(--danger); }
.main { flex: 1; padding: 28px 32px; overflow-x: hidden; min-width: 0; }
.state { padding: 60px; text-align: center; color: var(--text-dim); display: flex; flex-direction: column; align-items: center; gap: 14px; }
.state.err { color: var(--danger); }

/* Mobile-only shell pieces — hidden on desktop */
.topbar, .tabbar { display: none; }

@media (max-width: 760px) {
  .app { flex-direction: column; min-height: 100dvh; }
  .sidebar { display: none; }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 50;
    padding: 10px 14px;
    background: var(--sidebar);
    color: var(--sidebar-text);
    border-bottom: 1px solid var(--sidebar-hover);
  }
  .topbar-brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .topbar-brand .logo {
    width: 34px; height: 34px; border-radius: 8px;
    background: var(--accent); color: #fff;
    font-weight: 700; font-size: 12px;
    display: grid; place-items: center;
  }
  .topbar-brand .brand-name { font-size: 13px; font-weight: 700; color: var(--sidebar-text); line-height: 1.2; }
  .topbar-brand .brand-sub { font-size: 10px; color: var(--sidebar-dim); margin-top: 1px; letter-spacing: .04em; }
  .topbar-actions { display: flex; align-items: center; gap: 6px; }
  .topbar-actions .ic-btn {
    display: grid; place-items: center;
    width: 34px; height: 34px; border-radius: 8px;
    background: var(--sidebar-hover); border: 0;
    color: var(--sidebar-text); cursor: pointer;
  }
  .topbar-actions .avatar-sm {
    display: grid; place-items: center;
    width: 30px; height: 30px; border-radius: 50%;
    background: var(--accent); color: #fff;
    font-size: 11px; font-weight: 700;
  }

  .main {
    padding: 16px 14px calc(76px + env(safe-area-inset-bottom));
  }

  .tabbar {
    display: grid;
    grid-template-columns: repeat(3, 1fr) auto;
    align-items: center;
    gap: 4px;
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 60;
    padding: 8px 14px calc(8px + env(safe-area-inset-bottom));
    background: var(--surface);
    border-top: 1px solid var(--border);
    box-shadow: 0 -8px 24px rgba(15, 23, 42, .08);
  }
  .tab-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 6px 4px;
    text-decoration: none;
    color: var(--text-dim);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: .02em;
    border-radius: 8px;
  }
  .tab-item.router-link-exact-active { color: var(--accent); }
  .tab-item.router-link-exact-active::before {
    content: ''; display: block; position: absolute;
    margin-top: -8px; width: 22px; height: 2px;
    background: var(--accent); border-radius: 2px;
  }
  .tab-fab {
    display: grid; place-items: center;
    width: 46px; height: 46px; border-radius: 50%;
    margin-left: 6px;
    background: var(--accent); color: #fff;
    border: 0; cursor: pointer;
    box-shadow: 0 6px 18px rgba(20, 184, 166, .35);
  }
}
</style>

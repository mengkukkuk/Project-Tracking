import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('@/views/OverviewView.vue') },
  { path: '/pipeline', component: () => import('@/views/PipelineView.vue') },
  { path: '/pm-cards', redirect: { path: '/pipeline', query: { group: 'pm' } } },
  { path: '/table', component: () => import('@/views/TableView.vue') },
  { path: '/bom', component: () => import('@/views/BomGlobalView.vue') },
  { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
  { path: '/summaries', component: () => import('@/views/SummariesView.vue') },
  {
    path: '/users',
    component: () => import('@/views/UsersView.vue'),
    meta: { permission: 'roles.assign' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Auth guard: restore the session once, then gate non-public routes.
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()

  if (!to.meta.public && !auth.isAuthed) {
    return { path: '/login', query: to.path !== '/' ? { redirect: to.path } : undefined }
  }
  if (to.path === '/login' && auth.isAuthed) return { path: '/' }
  // Permission-gated routes — bounce to home if the live role lacks it.
  // (Backend still enforces on every request; this is just UX.)
  if (to.meta.permission && !auth.hasPermission(to.meta.permission)) {
    return { path: '/' }
  }
})

export default router

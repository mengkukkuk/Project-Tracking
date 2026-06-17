import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('@/views/OverviewView.vue') },
  { path: '/pipeline', component: () => import('@/views/PipelineView.vue') },
  { path: '/pm-cards', component: () => import('@/views/PmCardsView.vue') },
  { path: '/table', component: () => import('@/views/TableView.vue') },
  { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
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
})

export default router

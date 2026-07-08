import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { PAGES, pagePerm } from '@/constants/pages'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('@/views/OverviewView.vue'), meta: { permission: pagePerm('overview') } },
  { path: '/pipeline', component: () => import('@/views/PipelineView.vue'), meta: { permission: pagePerm('pipeline') } },
  { path: '/pm-cards', redirect: { path: '/pipeline', query: { group: 'pm' } } },
  { path: '/table', component: () => import('@/views/TableView.vue'), meta: { permission: pagePerm('table') } },
  { path: '/bom', component: () => import('@/views/BomGlobalView.vue'), meta: { permission: pagePerm('bom') } },
  { path: '/dashboard', component: () => import('@/views/DashboardView.vue'), meta: { permission: pagePerm('dashboard') } },
  { path: '/summaries', component: () => import('@/views/SummariesView.vue'), meta: { permission: pagePerm('summaries') } },
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

// First page whose permission the user currently holds, or null if none.
// Used as the redirect target instead of a hardcoded '/' so a user without
// page.overview doesn't bounce back into the same denied route.
function firstAllowedPath(auth) {
  const hit = PAGES.find((p) => auth.hasPermission(pagePerm(p.key)))
  return hit ? hit.path : null
}

// Auth guard: restore the session once, then gate non-public routes.
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()

  if (!to.meta.public && !auth.isAuthed) {
    return { path: '/login', query: to.path !== '/' ? { redirect: to.path } : undefined }
  }
  if (to.path === '/login' && auth.isAuthed) return { path: firstAllowedPath(auth) || '/' }
  // Permission-gated routes — bounce to the user's first allowed page if the
  // live role/override lacks it. (Backend still enforces on every request;
  // this is just UX.)
  if (to.meta.permission && !auth.hasPermission(to.meta.permission)) {
    const fallback = firstAllowedPath(auth)
    // A member always keeps at least one page server-side (422 guard on the
    // management endpoint), so this is only stale-local-state safety.
    if (!fallback) {
      auth.logout()
      return { path: '/login' }
    }
    return { path: fallback }
  }
})

export default router

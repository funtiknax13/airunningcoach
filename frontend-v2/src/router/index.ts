import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',            component: () => import('@/pages/LandingPage.vue') },
    { path: '/dashboard',   component: () => import('@/pages/DashboardPage.vue'),  meta: { auth: true } },
    { path: '/activities',  component: () => import('@/pages/ActivitiesPage.vue'), meta: { auth: true } },
    { path: '/training',    component: () => import('@/pages/TrainingPage.vue'),    meta: { auth: true } },
    { path: '/goals',       component: () => import('@/pages/GoalsPage.vue'),       meta: { auth: true } },
    { path: '/coach',       component: () => import('@/pages/CoachPage.vue'),       meta: { auth: true } },
    { path: '/subscription',  component: () => import('@/pages/SubscriptionPage.vue'), meta: { auth: true } },
    { path: '/payment/success', component: () => import('@/pages/PaymentSuccessPage.vue'), meta: { auth: true } },
    { path: '/auth/callback',   component: () => import('@/pages/AuthCallbackPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.user) {
    await auth.loadMe().catch(() => {})
  }
  // Авторизованных пользователей с главной → на дашборд
  if (to.path === '/' && auth.loggedIn) return '/dashboard'
  if (!to.meta.auth) return true
  if (!auth.loggedIn) return '/'
  return true
})

export default router

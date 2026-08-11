import { api, setToken } from './client'
import type {
  UserCreate, UserLogin, Token, UserResponse, UserUpdate, PasswordChange,
  Activity, ActivityDetail, ActivityCreate, ActivityUpdate, ActivityWithAnalysis,
  Goal, GoalCreate, GoalUpdate,
  Workout, WorkoutWithAnalysis,
  ChatMessage,
  DashboardInsights,
  MonthlyStats,
  RateLimitStatus,
  AchievementsResponse,
  SupportTicketSummary,
  SupportTicketDetail,
  AdminSupportList,
} from './types'

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (d: UserCreate) =>
    api.request<{ message: string; email: string }>('/api/auth/register', 'POST', d),

  login: async (d: UserLogin): Promise<Token> => {
    const token = await api.request<Token>('/api/auth/login', 'POST', d)
    setToken(token.access_token)
    return token
  },

  logout: () => setToken(null),

  // Короткий таймаут: это лёгкая проверка сессии, которая блокирует рендер всего
  // приложения (router.beforeEach ждёт её) — не должна висеть по 2 минуты, как AI-эндпоинты.
  me: () => api.request<UserResponse>('/api/auth/me', 'GET', undefined, 8_000),

  updateProfile: (d: UserUpdate) => api.request<UserResponse>('/api/auth/me', 'PATCH', d),

  changePassword: (d: PasswordChange) =>
    api.request<{ message: string }>('/api/auth/me/change-password', 'POST', d),

  forgotPassword: (email: string, lang = 'ru') =>
    api.request<{ message: string }>('/api/auth/forgot-password', 'POST', { email, lang }),

  resetPassword: (token: string, new_password: string, confirm_password: string) =>
    api.request<{ message: string }>('/api/auth/reset-password', 'POST',
      { token, new_password, confirm_password }),

  resendVerification: (email: string, password?: string) =>
    api.request<{ message: string }>(
      `/api/auth/resend-verification`, 'POST', { email, password }),

  getLimits: () => api.request<RateLimitStatus>('/api/auth/me/limits'),

}

// ── Activities ────────────────────────────────────────────────────────────
export const activitiesApi = {
  stats:  () => api.request<MonthlyStats>('/api/activities/stats'),
  list:   ()                        => api.request<Activity[]>('/api/activities'),
  create: (d: ActivityCreate)       => api.request<ActivityWithAnalysis>('/api/activities', 'POST', d),
  update: (id: number, d: ActivityUpdate) => api.request<Activity>(`/api/activities/${id}`, 'PUT', d),
  remove: (id: number)              => api.request<void>(`/api/activities/${id}`, 'DELETE'),
  detail: (id: number) => api.request<ActivityDetail>(`/api/activities/${id}/detail`),
  importFile: async (file: File): Promise<ActivityWithAnalysis> => {
    const form = new FormData()
    form.append('file', file)
    return api.requestRaw<ActivityWithAnalysis>('/api/activities/import', 'POST', form)
  },
  importUrl: (url: string): Promise<ActivityWithAnalysis> =>
    api.request<ActivityWithAnalysis>('/api/activities/import-url', 'POST', { url }),
}

// ── Goals ─────────────────────────────────────────────────────────────────
export const goalsApi = {
  list:       ()                  => api.request<Goal[]>('/api/goals'),
  create:     (d: GoalCreate)     => api.request<Goal>('/api/goals', 'POST', d),
  update:     (id: number, d: GoalUpdate) => api.request<Goal>(`/api/goals/${id}`, 'PUT', d),
  achieve:    (id: number)        => api.request<Goal>(`/api/goals/${id}/achieve`, 'PATCH'),
  abandon:    (id: number)        => api.request<Goal>(`/api/goals/${id}/abandon`, 'PATCH'),
  reactivate: (id: number)        => api.request<Goal>(`/api/goals/${id}/reactivate`, 'PATCH'),
  remove:     (id: number)        => api.request<void>(`/api/goals/${id}`, 'DELETE'),
  active:     ()                  => api.request<Goal>('/api/goals/active'),
}

// ── Training ──────────────────────────────────────────────────────────────
export const trainingApi = {
  list:         ()                => api.request<Workout[]>('/api/training/workouts'),
  // weeks: 1 (неделя, всем, синхронно) | 4 (месяц) | 12 (3 месяца) — только Premium,
  // в фоне. Ответ: {status:'done'} (неделя готова) | {status:'running'} (длинный план
  // собирается в фоне — готовность опрашиваем через planStatus).
  generatePlan: (weeks = 1)       => api.request<{ status: 'done' | 'running'; weeks: number }>(`/api/training/plans/generate?weeks=${weeks}`, 'POST'),
  planStatus:   ()                => api.request<{ status: 'idle' | 'running' | 'done' | 'failed'; weeks?: number }>('/api/training/plans/status'),
  completeWorkout: (id: number, notes?: string) =>
    api.request<WorkoutWithAnalysis>(`/api/training/workouts/${id}/complete?notes=${notes ?? ''}`, 'PUT'),
  uncompleteWorkout: (id: number) =>
    api.request<Workout>(`/api/training/workouts/${id}/uncomplete`, 'PUT'),
}

// ── Chat ──────────────────────────────────────────────────────────────────
export const chatApi = {
  history: ()                         => api.request<ChatMessage[]>('/api/chat/history'),
  send:    (message: string, lang = 'ru') =>
    api.request<ChatMessage>('/api/chat/message', 'POST',
      { message, context_type: 'general', lang }),
  unreadCount: () => api.request<{ count: number }>('/api/chat/unread-count'),
  markRead:    () => api.request<{ count: number }>('/api/chat/mark-read', 'POST'),
}

// ── Insights ──────────────────────────────────────────────────────────────
export const insightsApi = {
  dashboard: () => api.request<DashboardInsights>('/api/ai-insights/dashboard'),
}

// ── Support (сторона пользователя) ──────────────────────────────────────────
export const supportApi = {
  myTickets:   () => api.request<SupportTicketSummary[]>('/api/support/tickets'),
  createTicket: (body: string) =>
    api.request<SupportTicketSummary>('/api/support/tickets', 'POST', { body }),
  ticket:      (id: number) => api.request<SupportTicketDetail>(`/api/support/tickets/${id}`),
  reply:       (id: number, body: string) =>
    api.request<SupportTicketDetail>(`/api/support/tickets/${id}/messages`, 'POST', { body }),
  unreadCount: () => api.request<{ count: number }>('/api/support/tickets/unread-count'),
}

// ── Support (сторона сотрудника / Admin Tools) ──────────────────────────────
export const adminSupportApi = {
  list:        (status: 'all' | 'open' | 'closed' = 'all', page = 1) =>
    api.request<AdminSupportList>(`/api/admin/support?status=${status}&page=${page}`),
  ticket:      (id: number) => api.request<SupportTicketDetail>(`/api/admin/support/${id}`),
  reply:       (id: number, body: string) =>
    api.request<SupportTicketDetail>(`/api/admin/support/${id}/reply`, 'POST', { body }),
  toggleStatus: (id: number) =>
    api.request<SupportTicketDetail>(`/api/admin/support/${id}/status`, 'POST'),
  badgeCounts: () => api.request<{ tickets: number }>('/api/admin/support/badge-counts'),
}

// ── Push-уведомления ────────────────────────────────────────────────────────
export const pushApi = {
  vapidKey: () => api.request<{ key: string }>('/api/push/vapid-public-key'),
  subscribe: (sub: PushSubscriptionJSON) =>
    api.request<{ message: string }>('/api/push/subscribe', 'POST', sub),
  unsubscribe: (endpoint: string) =>
    api.request<{ message: string }>('/api/push/unsubscribe', 'POST', { endpoint }),
  test: () => api.request<{ sent: number }>('/api/push/test', 'POST'),
}

// ── Ачивки / разряды ЕВСК ────────────────────────────────────────────────────
export const achievementsApi = {
  list: () => api.request<AchievementsResponse>('/api/achievements'),
  unseenCount: () => api.request<{ count: number }>('/api/achievements/unseen-count'),
  markSeen:    () => api.request<{ count: number }>('/api/achievements/mark-seen', 'POST'),
}

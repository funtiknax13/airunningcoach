import { api, setToken } from './client'
import type {
  UserCreate, UserLogin, Token, UserResponse, UserUpdate, PasswordChange,
  Activity, ActivityDetail, ActivityCreate, ActivityUpdate, ActivityWithAnalysis,
  Goal, GoalCreate, GoalUpdate,
  TrainingPlan, Workout,
  ChatMessage,
  DashboardInsights,
  MonthlyStats,
  RateLimitStatus,
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

  me: () => api.request<UserResponse>('/api/auth/me'),

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
  activePlan:   ()                => api.request<TrainingPlan>('/api/training/plans/active'),
  generatePlan: ()                => api.request<TrainingPlan>('/api/training/plans/generate', 'POST'),
  completeWorkout: (id: number, notes?: string) =>
    api.request<Workout>(`/api/training/workouts/${id}/complete?notes=${notes ?? ''}`, 'PUT'),
  uncompleteWorkout: (id: number) =>
    api.request<Workout>(`/api/training/workouts/${id}/uncomplete`, 'PUT'),
}

// ── Chat ──────────────────────────────────────────────────────────────────
export const chatApi = {
  history: ()                         => api.request<ChatMessage[]>('/api/chat/history'),
  send:    (message: string, lang = 'ru') =>
    api.request<ChatMessage>('/api/chat/message', 'POST',
      { message, context_type: 'general', lang }),
}

// ── Insights ──────────────────────────────────────────────────────────────
export const insightsApi = {
  dashboard: () => api.request<DashboardInsights>('/api/ai-insights/dashboard'),
}

// ── Support ───────────────────────────────────────────────────────────────
export const supportApi = {
  contact: (subject: string, message: string, lang = 'ru') =>
    api.request<{ message: string }>('/api/support/contact', 'POST', { subject, message, lang }),
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

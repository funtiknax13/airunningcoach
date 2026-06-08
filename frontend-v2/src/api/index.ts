import { api, setToken } from './client'
import type {
  UserCreate, UserLogin, Token, UserResponse, UserUpdate, PasswordChange,
  Activity, ActivityDetail, ActivityCreate, ActivityUpdate,
  Goal, GoalCreate, GoalUpdate,
  TrainingPlan, Workout,
  ChatMessage,
  DashboardInsights,
  RateLimitStatus,
} from './types'

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (d: UserCreate) =>
    api.request<{ message: string; email: string }>('/auth/register', 'POST', d),

  login: async (d: UserLogin): Promise<Token> => {
    const token = await api.request<Token>('/auth/login', 'POST', d)
    setToken(token.access_token)
    return token
  },

  logout: () => setToken(null),

  me: () => api.request<UserResponse>('/auth/me'),

  updateProfile: (d: UserUpdate) => api.request<UserResponse>('/auth/me', 'PATCH', d),

  changePassword: (d: PasswordChange) =>
    api.request<{ message: string }>('/auth/me/change-password', 'POST', d),

  forgotPassword: (email: string, lang = 'ru') =>
    api.request<{ message: string }>('/auth/forgot-password', 'POST', { email, lang }),

  resetPassword: (token: string, new_password: string, confirm_password: string) =>
    api.request<{ message: string }>('/auth/reset-password', 'POST',
      { token, new_password, confirm_password }),

  resendVerification: (email: string) =>
    api.request<{ message: string }>(
      `/auth/resend-verification?email=${encodeURIComponent(email)}`, 'POST'),

  getLimits: () => api.request<RateLimitStatus>('/auth/me/limits'),
}

// ── Activities ────────────────────────────────────────────────────────────
export const activitiesApi = {
  list:   ()                        => api.request<Activity[]>('/activities'),
  create: (d: ActivityCreate)       => api.request<Activity>('/activities', 'POST', d),
  update: (id: number, d: ActivityUpdate) => api.request<Activity>(`/activities/${id}`, 'PUT', d),
  remove: (id: number)              => api.request<void>(`/activities/${id}`, 'DELETE'),
  detail: (id: number) => api.request<ActivityDetail>(`/activities/${id}/detail`),
  importFile: async (file: File): Promise<Activity> => {
    const form = new FormData()
    form.append('file', file)
    return api.requestRaw<Activity>('/activities/import', 'POST', form)
  },
}

// ── Goals ─────────────────────────────────────────────────────────────────
export const goalsApi = {
  list:       ()                  => api.request<Goal[]>('/goals'),
  create:     (d: GoalCreate)     => api.request<Goal>('/goals', 'POST', d),
  update:     (id: number, d: GoalUpdate) => api.request<Goal>(`/goals/${id}`, 'PUT', d),
  achieve:    (id: number)        => api.request<Goal>(`/goals/${id}/achieve`, 'PATCH'),
  abandon:    (id: number)        => api.request<Goal>(`/goals/${id}/abandon`, 'PATCH'),
  reactivate: (id: number)        => api.request<Goal>(`/goals/${id}/reactivate`, 'PATCH'),
  remove:     (id: number)        => api.request<void>(`/goals/${id}`, 'DELETE'),
  active:     ()                  => api.request<Goal>('/goals/active'),
}

// ── Training ──────────────────────────────────────────────────────────────
export const trainingApi = {
  activePlan:   ()                => api.request<TrainingPlan>('/training/plans/active'),
  generatePlan: ()                => api.request<TrainingPlan>('/training/plans/generate', 'POST'),
  completeWorkout: (id: number, notes?: string) =>
    api.request<Workout>(`/training/workouts/${id}/complete?notes=${notes ?? ''}`, 'PUT'),
  uncompleteWorkout: (id: number) =>
    api.request<Workout>(`/training/workouts/${id}/uncomplete`, 'PUT'),
}

// ── Chat ──────────────────────────────────────────────────────────────────
export const chatApi = {
  history: ()                         => api.request<ChatMessage[]>('/chat/history'),
  send:    (message: string, lang = 'ru') =>
    api.request<ChatMessage>('/chat/message', 'POST',
      { message, context_type: 'general', lang }),
}

// ── Insights ──────────────────────────────────────────────────────────────
export const insightsApi = {
  dashboard: () => api.request<DashboardInsights>('/ai-insights/dashboard'),
}

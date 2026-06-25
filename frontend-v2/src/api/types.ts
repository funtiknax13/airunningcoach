// ── Auth ──────────────────────────────────────────────────────────────────
export interface UserCreate {
  email: string
  password: string
  confirm_password: string
  name: string
  age?: number | null
  weight?: number | null
  height?: number | null
  lang?: string
}

export interface UserLogin {
  email: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: number
  email: string
  name: string
  age: number | null
  weight: number | null
  height: number | null
  is_verified: boolean
  is_premium: boolean
  premium_until: string | null
  fitness_level: string | null
  running_goal: string | null
  weekly_km: number | null
  training_days: number | null
  onboarding_completed: boolean
  created_at: string
}

export interface UsageStat {
  used: number
  limit: number
  window: 'hour' | 'day'
  tier: 'basic' | 'premium'
}

export interface RateLimitStatus {
  is_premium: boolean
  premium_until: string | null
  chat: UsageStat
  plan: UsageStat
}

export interface UserUpdate {
  name?: string
  age?: number | null
  weight?: number | null
  height?: number | null
  fitness_level?: string | null
  running_goal?: string | null
  weekly_km?: number | null
  training_days?: number | null
  onboarding_completed?: boolean
}

export interface PasswordChange {
  current_password: string
  new_password: string
  confirm_password: string
}

// ── Activities ────────────────────────────────────────────────────────────
export interface ActivityCreate {
  date: string
  distance_km: number
  duration_min: number
  avg_heart_rate?: number | null
  calories?: number | null
  notes?: string | null
  activity_type?: string
  source?: string
}

export interface ActivityUpdate {
  date?: string
  distance_km?: number
  duration_min?: number
  avg_heart_rate?: number | null
  notes?: string | null
  activity_type?: string
}

export interface ActivityLap {
  num: number
  dist_km: number
  dur_min: number | null
  pace: number | null
  avg_hr: number | null
  max_hr: number | null
}

export interface ActivitySplit {
  km: number
  pace: number | null
  avg_hr: number | null
}

export interface ActivityTrackPoint {
  t: number | null
  lat: number
  lon: number
  dist: number
  ele?: number
  hr?: number
}

export interface Activity {
  id: number
  user_id: number
  date: string
  distance_km: number
  duration_min: number
  pace_min_per_km: number
  avg_heart_rate: number | null
  max_heart_rate: number | null
  avg_cadence: number | null
  elevation_gain: number | null
  calories: number | null
  notes: string | null
  activity_type: string
  source: string
  laps: ActivityLap[] | null
  splits: ActivitySplit[] | null
  created_at: string
}

export interface ActivityDetail extends Activity {
  track_points: ActivityTrackPoint[] | null
}

export interface ActivityWithAnalysis extends Activity {
  ai_analysis: string | null
}

// ── Goals ─────────────────────────────────────────────────────────────────
export type GoalType = 'half_marathon' | 'full_marathon' | '10k' | '5k' | 'custom'

export interface GoalCreate {
  goal_type: GoalType
  target_distance_km?: number | null
  target_time_min?: number | null
  target_date?: string | null
  description?: string | null
}

export interface GoalUpdate {
  goal_type?: GoalType
  target_distance_km?: number | null
  target_time_min?: number | null
  target_date?: string | null
  description?: string | null
}

export interface Goal {
  id: number
  user_id: number
  goal_type: GoalType
  target_distance_km: number | null
  target_time_min: number | null
  target_date: string | null
  description: string | null
  is_active: boolean
  is_achieved: boolean
  is_abandoned: boolean
  created_at: string
}

// ── Training ──────────────────────────────────────────────────────────────
export type WorkoutType = 'easy' | 'tempo' | 'interval' | 'long' | 'recovery' | 'rest'
export type CompletionStatus = 'none' | 'completed' | 'approximate'

export interface Workout {
  id: number
  day_of_week: number
  planned_date: string | null
  workout_type: WorkoutType
  description: string
  distance_km: number | null
  target_pace_min_km: number | null
  duration_min: number | null
  completed: boolean
  completion_status: CompletionStatus
  notes_after: string | null
}

export interface TrainingPlan {
  id: number
  week_start_date: string
  week_end_date: string
  goal_type: string
  is_active: boolean
  created_at: string
  workouts: Workout[]
}

// ── Chat ──────────────────────────────────────────────────────────────────
export interface ChatMessage {
  id: number
  role: 'user' | 'ai' | 'system'
  content: string
  context_type: string | null
  created_at: string
}

// ── Insights ──────────────────────────────────────────────────────────────
export interface DashboardStats {
  total_distance_km: number
  total_time_min: number
  average_pace_min_km: number
  activities_count: number
  average_weekly_distance: number
}

export interface DashboardInsights {
  user_name: string
  statistics: DashboardStats
  active_goal: { type: string; description: string } | null
  ai_insights: string[]
}

export interface MonthlyStats {
  period: string
  total_distance_km: number
  total_time_min: number
  average_pace_min_km: number
  activities_count: number
  prev_distance_km: number
  distance_delta: number
}

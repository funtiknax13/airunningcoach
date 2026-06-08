<template>
  <AppLayout>
    <div class="dash-grid">

      <!-- Left column -->
      <div class="dash-col">

        <!-- Stats -->
        <div v-if="pageLoading" class="card" style="padding:16px">
          <SkeletonLoader type="stat-grid" :count="4" />
        </div>
        <div v-else class="stat-grid">
          <div class="stat-card">
            <div class="stat-card-label"><i class="fas fa-road"></i> {{ $t('stats.km') }}</div>
            <div class="stat-card-value">
              {{ stats?.total_distance_km.toFixed(1) ?? '—' }}
              <span class="stat-card-unit">km</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-card-label"><i class="fas fa-tachometer-alt"></i> {{ $t('stats.pace') }}</div>
            <div class="stat-card-value">
              {{ formatPace(stats?.average_pace_min_km) }}
              <span class="stat-card-unit">/km</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-card-label"><i class="fas fa-calendar-check"></i> {{ $t('stats.count') }}</div>
            <div class="stat-card-value">{{ stats?.activities_count ?? '—' }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-label"><i class="fas fa-clock"></i> {{ $t('stats.time') }}</div>
            <div class="stat-card-value">
              {{ formatTime(stats?.total_time_min) }}
            </div>
          </div>
        </div>

        <!-- Recent runs -->
        <div class="card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-person-running"></i> {{ $t('dash.recentRuns') }}</div>
            <RouterLink to="/activities" class="btn btn-ghost btn-sm">
              {{ $t('dash.viewAll') }} →
            </RouterLink>
          </div>
          <SkeletonLoader v-if="pageLoading" type="dash-runs" :count="4" />
          <div v-else-if="!recentActivities.length" class="empty-state">
            <i class="fas fa-person-running"></i>
            <p>{{ $t('activities.empty') }}</p>
          </div>
          <div v-else v-for="act in recentActivities" :key="act.id" class="activity-row">
            <div class="activity-row-icon"><i class="fas fa-person-running"></i></div>
            <div class="activity-row-info">
              <div class="activity-row-date">{{ formatDate(act.date) }}</div>
              <div class="activity-row-note">{{ act.notes || $t('dash.run') }}</div>
            </div>
            <div class="activity-row-stats">
              <div class="activity-stat">
                <span class="activity-stat-val" style="color:var(--brand)">{{ act.distance_km }}</span>
                <span class="activity-stat-lbl">km</span>
              </div>
              <div class="activity-stat">
                <span class="activity-stat-val">{{ formatPace(act.pace_min_per_km) }}</span>
                <span class="activity-stat-lbl">{{ $t('stats.pace') }}</span>
              </div>
              <div class="activity-stat">
                <span class="activity-stat-val">{{ formatDuration(act.duration_min) }}</span>
                <span class="activity-stat-lbl">{{ $t('stats.time') }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Active goals -->
        <div class="card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-bullseye"></i> {{ $t('dash.activeGoals') }}</div>
            <RouterLink to="/goals" class="btn btn-ghost btn-sm">
              {{ $t('dash.viewAll') }} →
            </RouterLink>
          </div>
          <SkeletonLoader v-if="pageLoading" type="goal-list" :count="2" />
          <div v-else-if="!activeGoals.length" class="empty-state">
            <i class="fas fa-bullseye"></i>
            <p>{{ $t('goals.empty') }}</p>
          </div>
          <div v-else v-for="g in activeGoals" :key="g.id" class="goal-item">
            <div class="goal-item-header">
              <span class="goal-item-title">{{ g.description || goalTypeLabel(g.goal_type) }}</span>
              <span class="badge badge-active">{{ $t('goals.status.active') }}</span>
            </div>
            <div class="goal-item-meta">
              <span v-if="g.target_distance_km">🏃 {{ g.target_distance_km }} km</span>
              <span v-if="g.target_time_min">⏱ {{ formatGoalTime(g.target_time_min) }}</span>
              <span v-if="g.target_date">📅 {{ formatDate(g.target_date) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right column -->
      <div class="dash-col">

        <!-- Today's workout -->
        <div class="card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-calendar-day"></i> {{ $t('dash.today') }}</div>
            <RouterLink to="/training" class="btn btn-ghost btn-sm">{{ $t('dash.fullPlan') }}</RouterLink>
          </div>
          <SkeletonLoader v-if="pageLoading" type="workout-list" :count="1" />
          <div v-else-if="!todayWorkout" class="empty-state" style="padding:20px 0">
            <i class="fas fa-calendar-week"></i>
            <p>{{ $t('dash.noPlan') }}</p>
            <RouterLink to="/training" class="btn btn-primary btn-sm" style="margin-top:10px;display:inline-flex">
              {{ $t('plan.generate') }}
            </RouterLink>
          </div>
          <div v-else-if="todayWorkout" class="workout-row" style="padding-top:0">
            <div class="workout-date-block">
              <span class="workout-day-num">{{ todayDayNum }}</span>
              <span class="workout-month">{{ todayMonth }}</span>
              <span class="workout-day-name">{{ todayDayName }}</span>
            </div>
            <div class="workout-body">
              <span class="workout-type-badge" :class="`badge-type-${todayWorkout.workout_type}`">
                {{ $t(`plan.type.${todayWorkout.workout_type}`) }}
              </span>
              <div class="workout-text">{{ todayWorkout.description }}</div>
              <div class="workout-chips">
                <span v-if="todayWorkout.distance_km" class="workout-chip">
                  📏 {{ todayWorkout.distance_km }} km
                </span>
                <span v-if="todayWorkout.target_pace_min_km" class="workout-chip">
                  ⏱ {{ formatPaceNum(todayWorkout.target_pace_min_km) }}/km
                </span>
              </div>
            </div>
            <div class="workout-action">
              <span v-if="todayWorkout.completion_status === 'completed'" class="badge badge-done">✓</span>
              <span v-else-if="todayWorkout.completion_status === 'approximate'" class="badge badge-approx">~</span>
            </div>
          </div>
        </div>

        <!-- AI Insights -->
        <div class="card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-brain"></i> {{ $t('ai.title') }}</div>
            <RouterLink to="/coach" class="btn btn-ghost btn-sm">{{ $t('dash.toCoach') }}</RouterLink>
          </div>
          <SkeletonLoader v-if="pageLoading" type="insights" :count="3" />
          <div v-else-if="!insights.data?.ai_insights?.length" class="empty-state" style="padding:16px 0">
            <i class="fas fa-robot"></i>
            <p>{{ $t('ai.empty') }}</p>
          </div>
          <div v-else v-for="(item, i) in insights.data?.ai_insights?.slice(0,3)" :key="i" class="insight-item">
            <i class="fas fa-lightbulb"></i>
            {{ item }}
          </div>
        </div>

      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import { useActivitiesStore } from '@/stores/activities'
import { useGoalsStore }      from '@/stores/goals'
import { useInsightsStore }   from '@/stores/insights'
import { useTrainingStore }   from '@/stores/training'
import type { GoalType } from '@/api/types'

const { t, locale } = useI18n()
const activities = useActivitiesStore()
const goals      = useGoalsStore()
const insights   = useInsightsStore()
const training   = useTrainingStore()

const pageLoading = ref(true)

onMounted(async () => {
  await Promise.all([activities.load(), goals.load(), training.load(), insights.load()])
  pageLoading.value = false
})

const stats = computed(() => insights.data?.statistics)
const recentActivities = computed(() => activities.all.slice(0, 4))
const activeGoals = computed(() => goals.goals.filter(g => !g.is_achieved && !g.is_abandoned).slice(0, 3))

const todayWorkout = computed(() => {
  if (!training.plan?.workouts) return null
  const today = new Date().toDateString()
  return training.plan.workouts.find(w => {
    if (!w.planned_date) return false
    return new Date(w.planned_date).toDateString() === today
  }) ?? null
})

const todayDayNum  = computed(() => new Date().getDate())
const todayDayName = computed(() => {
  const days = locale.value === 'ru'
    ? ['Вс','Пн','Вт','Ср','Чт','Пт','Сб']
    : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
  return days[new Date().getDay()]
})
const todayMonth = computed(() => {
  const months = locale.value === 'ru'
    ? ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
    : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[new Date().getMonth()]
})

function formatPace(p?: number) {
  if (!p) return '—'
  const m = Math.floor(p); const s = Math.round((p-m)*60)
  return `${m}:${String(s).padStart(2,'0')}`
}
function formatPaceNum(p: number) {
  const m = Math.floor(p); const s = Math.round((p-m)*60)
  return `${m}:${String(s).padStart(2,'0')}`
}
function formatTime(min?: number) {
  if (!min) return '—'
  const h = Math.floor(min/60); const m = Math.round(min%60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function formatDuration(min: number) {
  const h = Math.floor(min/60); const m = Math.round(min%60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(locale.value === 'ru' ? 'ru-RU' : 'en-US', { day:'2-digit', month:'short' })
}
function formatGoalTime(min: number) {
  const h = Math.floor(min/60); const m = Math.round(min%60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function goalTypeLabel(type: GoalType) {
  const map: Record<string, string> = {
    half_marathon: t('goals.type.half_marathon'), full_marathon: t('goals.type.full_marathon'),
    '10k': t('goals.type.10k'), '5k': t('goals.type.5k'), custom: t('goals.type.custom'),
  }
  return map[type] ?? type
}
</script>

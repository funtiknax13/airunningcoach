<template>
  <div class="card">
    <div class="card-title">
      <i class="fas fa-calendar-week"></i> {{ $t('plan.title') }}
      <button class="btn-primary" style="margin-left:auto"
              @click="store.generate()" :disabled="store.loading">
        <i :class="store.loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
        {{ store.loading ? $t('plan.generating') : $t('plan.generate') }}
      </button>
    </div>

    <p v-if="!store.plan" style="color:#94a3b8;padding:8px 0;">{{ $t('plan.empty') }}</p>

    <template v-else>
      <div v-for="w in sortedWorkouts" :key="w.id"
           class="workout-item" :class="{ 'workout-item--rest': isRest(w.workout_type) }">
        <div class="workout-date-col">
          <span class="workout-date">{{ workoutDate(w) }}</span>
          <span class="workout-dayname">{{ dayName(w.day_of_week) }}</span>
        </div>
        <div class="workout-desc">
          <span class="workout-type-label" :class="`workout-type--${w.workout_type}`">
            {{ $t(`plan.type.${w.workout_type}`) }}
          </span>
          <span class="workout-text">{{ w.description }}</span>
          <div class="wo-chips">
            <span v-if="w.distance_km" class="wo-chip">📏 {{ w.distance_km }} km</span>
            <span v-if="w.target_pace_min_km" class="wo-chip">⏱ {{ formatPace(w.target_pace_min_km) }}/km</span>
          </div>
        </div>
        <div class="workout-status">
          <span v-if="w.completion_status === 'completed'" class="workout-badge workout-badge--done">
            {{ $t('plan.status.done') }}
          </span>
          <span v-else-if="w.completion_status === 'approximate'" class="workout-badge workout-badge--approx">
            {{ $t('plan.status.approx') }}
          </span>
          <button v-else class="complete-workout" @click="complete(w.id)">
            {{ $t('plan.status.mark') }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTrainingStore } from '@/stores/training'
import { useI18n } from 'vue-i18n'
import type { WorkoutType } from '@/api/types'

const store = useTrainingStore()
const { t } = useI18n()

const DAYS_RU = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
const DAYS_EN = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
const RUNNING: WorkoutType[] = ['easy','tempo','interval','long','recovery']

const sortedWorkouts = computed(() =>
  [...(store.plan?.workouts ?? [])].sort((a, b) => {
    if (a.planned_date && b.planned_date)
      return new Date(a.planned_date).getTime() - new Date(b.planned_date).getTime()
    return a.day_of_week - b.day_of_week
  })
)

function isRest(type: WorkoutType) { return !RUNNING.includes(type) }
function dayName(dow: number) {
  const locale = document.documentElement.lang
  return locale === 'ru' ? DAYS_RU[dow] : DAYS_EN[dow]
}
function workoutDate(w: { planned_date: string | null }) {
  if (!w.planned_date) return '—'
  return new Date(w.planned_date).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })
}
function formatPace(pace: number) {
  const m = Math.floor(pace); const s = Math.round((pace - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
async function complete(id: number) {
  const notes = prompt(t('plan.workout.notes')) ?? undefined
  await store.completeWorkout(id, notes)
}
</script>

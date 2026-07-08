<template>
  <AppLayout>
    <template #header-actions>
      <button class="btn btn-primary btn-sm" @click="onGenerate" :disabled="store.loading">
        <i :class="store.loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
        {{ store.loading ? $t('plan.generating') : $t('plan.generate') }}
      </button>
    </template>

    <div class="card">
      <div class="card-header">
        <div class="card-title"><i class="fas fa-calendar-week"></i> {{ $t('plan.title') }}</div>
        <span v-if="store.all.length" style="font-size:0.78rem;color:var(--text-3)">
          {{ planDateRange }}
        </span>
      </div>

      <SkeletonLoader v-if="store.loadingPlan" type="workout-list" :count="7" />
      <div v-else-if="!store.all.length" class="empty-state" style="padding:40px 0">
        <i class="fas fa-calendar-week"></i>
        <p>{{ $t('plan.empty') }}</p>
        <button class="btn btn-primary" style="margin-top:14px" @click="onGenerate" :disabled="store.loading">
          <i class="fas fa-robot"></i>
          {{ $t('plan.generate') }}
        </button>
      </div>

      <template v-else>
        <div v-for="w in sortedWorkouts" :key="w.id"
             class="workout-row" :class="{ 'workout-row--rest': isRest(w.workout_type) }">
          <div class="workout-date-block">
            <span class="workout-day-num">{{ wDayNum(w) }}</span>
            <span class="workout-month">{{ wMonth(w) }}</span>
            <span class="workout-day-name">{{ wDayName(w) }}</span>
          </div>
          <div class="workout-body">
            <span class="workout-type-badge" :class="`badge-type-${w.workout_type}`">
              {{ $t(`plan.type.${w.workout_type}`) }}
            </span>
            <div class="workout-text">{{ w.description }}</div>
            <div class="workout-chips">
              <span v-if="w.distance_km" class="workout-chip">📏 {{ w.distance_km }} km</span>
              <span v-if="w.target_pace_min_km" class="workout-chip">⏱ {{ formatPace(w.target_pace_min_km) }}/km</span>
            </div>
          </div>
          <div class="workout-action">
            <!-- Rest day: nothing to confirm, no button at all -->
            <span v-if="isRest(w.workout_type)" class="badge badge-rest">
              <i class="fas fa-moon"></i> {{ $t('plan.status.restDay') }}
            </span>
            <!-- Completed: badge + undo button -->
            <template v-else-if="w.completion_status === 'completed' || w.completion_status === 'approximate'">
              <span class="badge" :class="w.completion_status === 'completed' ? 'badge-done' : 'badge-approx'">
                {{ w.completion_status === 'completed' ? $t('plan.status.done') : $t('plan.status.approx') }}
              </span>
              <button class="btn-uncomplete" @click="uncomplete(w.id)" :title="$t('plan.status.undoTitle')">
                <i class="fas fa-rotate-left"></i>
              </button>
            </template>
            <!-- Checked, but no matching run found (or way off plan) — let them retry -->
            <template v-else-if="w.completion_status === 'unconfirmed'">
              <span class="badge badge-unconfirmed">{{ $t('plan.status.unconfirmed') }}</span>
              <button class="btn-complete" @click="complete(w.id)">
                <i class="fas fa-rotate-right"></i>
                {{ $t('plan.status.retry') }}
              </button>
            </template>
            <!-- Future workout: disabled with tooltip -->
            <button v-else-if="isFuture(w)" class="btn-complete btn-complete--future" disabled :title="$t('plan.status.futureTitle')">
              <i class="fas fa-lock"></i>
              {{ $t('plan.status.mark') }}
            </button>
            <!-- Available to mark -->
            <button v-else class="btn-complete" @click="complete(w.id)">
              <i class="fas fa-check"></i>
              {{ $t('plan.status.mark') }}
            </button>
          </div>
        </div>

        <div v-if="pages > 1" class="pager">
          <button class="pager-btn" :disabled="page === 0" @click="page--">
            <i class="fas fa-chevron-left"></i>
          </button>
          <span class="pager-info">{{ page + 1 }} / {{ pages }}</span>
          <button class="pager-btn" :disabled="page >= pages - 1" @click="page++">
            <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import { useTrainingStore } from '@/stores/training'
import { useDialog } from '@/composables/useDialog'
import type { WorkoutType } from '@/api/types'

const { t, locale } = useI18n()
const store = useTrainingStore()

onMounted(() => store.load())
const { prompt, confirm } = useDialog()

const RUNNING: WorkoutType[] = ['easy','tempo','interval','long','recovery']
const DAYS_RU = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб']
const DAYS_EN = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
const MON_RU  = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
const MON_EN  = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

const PAGE_SIZE = 7
const page = ref(0)

// store.all отсортирован сервером по planned_date desc, так что страница 0 —
// это всегда 7 самых дальних по дате тренировок, то есть актуальный план
// (см. комментарий в training.py). Дальше по страницам — история.
const pages = computed(() => Math.max(1, Math.ceil(store.all.length / PAGE_SIZE)))
const pagedItems = computed(() =>
  store.all.slice(page.value * PAGE_SIZE, (page.value + 1) * PAGE_SIZE)
)

const sortedWorkouts = computed(() =>
  [...pagedItems.value].sort((a, b) => {
    if (a.planned_date && b.planned_date)
      return new Date(a.planned_date).getTime() - new Date(b.planned_date).getTime()
    return a.day_of_week - b.day_of_week
  })
)

const planDateRange = computed(() => {
  if (!sortedWorkouts.value.length) return ''
  const dated = sortedWorkouts.value.filter(w => w.planned_date)
  if (!dated.length) return ''
  const s = new Date(dated[0].planned_date!)
  const e = new Date(dated[dated.length - 1].planned_date!)
  const fmt = (d: Date) => d.toLocaleDateString(locale.value === 'ru' ? 'ru-RU' : 'en-US', { day:'numeric', month:'short' })
  return `${fmt(s)} — ${fmt(e)}`
})

function isRest(type: WorkoutType) { return !RUNNING.includes(type) }
function wDayNum(w: { planned_date: string|null }) {
  if (!w.planned_date) return '—'
  return new Date(w.planned_date).getDate()
}
function wMonth(w: { planned_date: string|null }) {
  if (!w.planned_date) return ''
  const m = new Date(w.planned_date).getMonth()
  return locale.value === 'ru' ? MON_RU[m] : MON_EN[m]
}
function wDayName(w: { planned_date: string|null; day_of_week: number }) {
  if (w.planned_date) {
    const d = new Date(w.planned_date).getDay()
    return locale.value === 'ru' ? DAYS_RU[d] : DAYS_EN[d]
  }
  return locale.value === 'ru' ? DAYS_RU[w.day_of_week] : DAYS_EN[w.day_of_week]
}
function formatPace(p: number) {
  const m = Math.floor(p); const s = Math.round((p-m)*60)
  return `${m}:${String(s).padStart(2,'0')}`
}
/** Returns true if the workout is scheduled for a future date (after today) */
function isFuture(w: { planned_date: string | null }): boolean {
  if (!w.planned_date) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(w.planned_date)
  d.setHours(0, 0, 0, 0)
  return d > today
}

async function onGenerate() {
  page.value = 0
  await store.generate()
}

async function complete(id: number) {
  // prompt() returns null when user clicks Cancel — must not mark workout as done
  const notes = await prompt(t('plan.workout.notes'), {
    placeholder: t('plan.workout.notesPlaceholder'),
    confirmLabel: t('plan.status.mark'),
    cancelLabel: t('btn.cancel'),
  })
  if (notes === null) return   // user cancelled — do NOT mark as done
  await store.completeWorkout(id, notes || undefined)
}

async function uncomplete(id: number) {
  const ok = await confirm(t('plan.status.undoConfirm'), {
    cancelLabel: t('btn.cancel'),
    confirmLabel: t('plan.status.undoBtn'),
  })
  if (!ok) return
  await store.uncompleteWorkout(id)
}
</script>

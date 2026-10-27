<template>
  <div class="plan-proposal">
    <div v-for="(w, i) in days" :key="i" class="pp-day" :class="{ 'pp-day--rest': w.workout_type === 'rest' }">
      <span class="pp-wd">{{ weekday(i) }}</span>
      <span class="pp-type">{{ typeLabel(w) }}</span>
      <span v-if="amount(w)" class="pp-amount">{{ amount(w) }}</span>
      <WorkoutSegments v-if="(resolved(w)?.segments.length ?? 0) > 1" :resolved="resolved(w)!" compact />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import WorkoutSegments from '@/components/training/WorkoutSegments.vue'
import type { PlanDraft, PlanDraftWorkout, WorkoutResolved } from '@/api/types'
import { isV2, fmtDuration } from '@/utils/plan'

const props = defineProps<{ draft: PlanDraft }>()
const { t, locale } = useI18n()

// Превью — одна неделя, даже если черновик на месяц: дальше недели структура
// только повторяется с ростом объёма, смысла показывать 28 строк в чате нет.
const days = computed(() => props.draft.workouts.slice(0, 7))

function weekday(i: number): string {
  const d = new Date(props.draft.start)
  d.setDate(d.getDate() + i)
  return d.toLocaleDateString(locale.value, { weekday: 'short' })
}

function typeLabel(w: PlanDraftWorkout): string {
  return t(`plan.type.${w.workout_type}`)
}

function resolved(w: PlanDraftWorkout): WorkoutResolved | null {
  return isV2(w.plan_structure) ? w.plan_structure.resolved : null
}

function amount(w: PlanDraftWorkout): string {
  if (w.workout_type === 'rest') return ''
  const r = resolved(w)
  const km = t('plan.unit.km')
  const dist = r?.distance_km ?? w.distance_km
  if (dist != null) return `${Math.round(dist * 10) / 10} ${km}`
  const dur = fmtDuration(r?.duration_min ?? w.duration_min, t('plan.unit.h'), t('plan.unit.min'))
  return dur ?? ''
}
</script>

<style scoped>
.plan-proposal {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  border: 1px solid var(--border);
  display: grid;
  gap: 7px;
}
.pp-day { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; font-size: 0.8rem; }
.pp-day--rest { color: var(--text-3); }
.pp-wd { font-weight: 700; min-width: 28px; color: var(--text); }
.pp-type { color: var(--text-2); }
.pp-amount { color: var(--text-2); font-variant-numeric: tabular-nums; }
.pp-day > :deep(.ws) { flex-basis: 100%; margin-top: 2px; }
</style>

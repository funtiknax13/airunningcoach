<template>
  <div v-if="hasContent" class="wm">
    <div v-if="chips.length" class="wm-chips">
      <span v-for="(c, i) in chips" :key="i" class="workout-chip" :class="{ 'wm-chip--muted': c.muted }"
        :title="c.title">{{ c.text }}</span>
    </div>
    <WorkoutSegments v-if="showBar" :resolved="v2!.resolved" :compact="compact" />
    <p v-if="comment && !compact" class="wm-comment"><i class="fas fa-comment-dots"></i> {{ comment }}</p>
    <p v-if="legacyText && !compact" class="wm-legacy">{{ legacyText }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import WorkoutSegments from '@/components/training/WorkoutSegments.vue'
import type { Workout, PlanStructure } from '@/api/types'
import { isV2, isLegacy, fmtRange, fmtHr, fmtDuration } from '@/utils/plan'
import { fmtPace } from '@/utils/activityNarrative'

const props = defineProps<{ workout: Workout; compact?: boolean }>()
const { t } = useI18n()

const v2 = computed(() => (isV2(props.workout.plan_structure) ? props.workout.plan_structure : null))
const isRest = computed(() => props.workout.workout_type === 'rest')

const showBar = computed(() => !!v2.value && v2.value.resolved.segments.length >= 1)
const comment = computed(() => v2.value?.comment || null)

const chips = computed(() => {
  const w = props.workout
  if (isRest.value) return []
  const out: { text: string; title?: string; muted?: boolean }[] = []
  const km = t('plan.unit.km')

  if (v2.value) {
    const r = v2.value.resolved
    const single = r.segments.length === 1 ? r.segments[0] : null
    if (r.distance_km != null) out.push({ text: `📏 ${Math.round(r.distance_km * 10) / 10} ${km}` })
    const dur = fmtDuration(r.duration_min, t('plan.unit.h'), t('plan.unit.min'))
    if (dur) out.push({ text: `⏱ ${dur}` })
    if (single && single.pace) {
      out.push({ text: `${fmtRange(single.pace)}/${km}`, title: t('plan.paceRangeTitle') })
    } else if (r.avg_pace != null) {
      out.push({ text: `≈ ${fmtPace(r.avg_pace)}/${km}`, title: t('plan.avgPaceTitle') })
    } else if (r.distance_km != null || r.duration_min != null) {
      out.push({ text: t('plan.byFeel'), title: t('plan.byFeelTitle'), muted: true })
    }
    if (single && single.hr) {
      const approx = r.hr_confidence === 'low' ? '≈' : ''
      out.push({ text: `♥ ${approx}${fmtHr(single.hr)}`, title: t('plan.hrTitle') })
    }
    return out
  }

  // Старые планы (без отрезков): как раньше — дистанция и целевой темп.
  if (w.distance_km) out.push({ text: `📏 ${w.distance_km} ${km}` })
  if (w.target_pace_min_km) out.push({ text: `⏱ ${fmtPace(w.target_pace_min_km)}/${km}` })
  return out
})

const legacyText = computed(() => {
  const ps = props.workout.plan_structure
  if (!isLegacy(ps)) return ''
  return formatLegacy(ps)
})

function formatLegacy(ps: PlanStructure): string {
  const parts: string[] = []
  if (ps.warmup_km) parts.push(`${t('plan.seg.warmup').toLowerCase()} ${ps.warmup_km} ${t('plan.unit.km')}`)
  for (const b of ps.main) {
    let s = `${b.reps}× ${b.distance_m}${t('plan.unit.m')}`
    if (b.target_pace_min_km) s += ` @${fmtPace(b.target_pace_min_km)}/${t('plan.unit.km')}`
    if (b.recovery_m) s += `, ${t('plan.seg.rest')} ${b.recovery_m}${t('plan.unit.m')}`
    parts.push(s)
  }
  if (ps.cooldown_km) parts.push(`${t('plan.seg.cooldown').toLowerCase()} ${ps.cooldown_km} ${t('plan.unit.km')}`)
  return parts.join(' · ')
}

const hasContent = computed(() => chips.value.length > 0 || showBar.value || !!comment.value || !!legacyText.value)
</script>

<style scoped>
.wm { margin-top: 6px; }
.wm-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.wm-chip--muted { color: var(--text-3); font-style: italic; }
.wm-comment {
  margin: 10px 0 0; padding: 8px 10px; border-radius: 8px; font-size: 0.8rem; line-height: 1.45;
  color: var(--text-2); background: var(--surface-2);
}
.wm-comment i { color: var(--brand); margin-right: 6px; }
.wm-legacy { margin: 4px 0 0; font-size: 0.78rem; line-height: 1.4; color: var(--text-3); }
</style>

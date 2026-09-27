<template>
  <div class="ws" :class="{ 'ws--compact': compact }">
    <div class="ws-bar" role="img" :aria-label="t('plan.seg.barLabel')">
      <span v-for="(b, i) in blocks" :key="i" class="ws-block"
        :style="{ flex: b.weight, background: b.color, '--lift': b.lift }" :title="b.title"></span>
    </div>
    <ul v-if="showLegend" class="ws-legend">
      <li v-for="(s, i) in resolved.segments" :key="i" class="ws-item">
        <span class="ws-dot" :style="{ background: zoneColor(s) }"></span>
        <span class="ws-name">{{ t(segmentTitleKey(s)) }}</span>
        <span class="ws-amount">{{ amount(s) }}</span>
        <span v-if="paceText(s)" class="ws-pace">{{ paceText(s) }}</span>
        <span v-else-if="s.kind !== 'walk'" class="ws-pace ws-feel">{{ t('plan.byFeel') }}</span>
        <span v-if="s.hr" class="ws-hr"><i class="fas fa-heart"></i> {{ resolved.hr_confidence === 'low' ? '≈' : '' }}{{ fmtHr(s.hr) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResolvedSegment, WorkoutResolved } from '@/api/types'
import { fmtRange, fmtHr, fmtSeconds, zoneColor, zoneColorByKey, zoneLift, WALK_COLOR, segmentWeight, segmentTitleKey } from '@/utils/plan'

const props = defineProps<{ resolved: WorkoutResolved; compact?: boolean }>()
const { t } = useI18n()

const km = () => t('plan.unit.km')
const minU = () => t('plan.unit.min')
const secU = () => t('plan.unit.sec')

// Легенда нужна только составным тренировкам; лёгкая/длинная — один сплошной отрезок.
const showLegend = computed(() => !props.compact && props.resolved.segments.length > 1)

interface Block { weight: number; color: string; lift: number; title: string }

// Сегменты графика. Интервалы и бег/ходьба раскладываются на отдельные повторы с
// паузами между ними, чтобы сразу было видно «5 интервалов»; остальное — один блок.
const blocks = computed<Block[]>(() => {
  const out: Block[] = []
  for (const s of props.resolved.segments) {
    const total = segmentWeight(s)
    const title = `${t(segmentTitleKey(s))} · ${amount(s)}`
    if (s.kind === 'intervals' && s.reps) {
      const rep = s.distance_m ?? (s.duration_s ?? 0) * 3
      const rec = s.recovery ? (s.recovery.distance_m ?? (s.recovery.duration_s ?? 0) * 3) : 0
      const per = total / (s.reps * (rep + rec || 1))
      const recColor = zoneColorByKey(s.recovery?.zone ?? 'recovery')
      for (let i = 0; i < s.reps; i++) {
        out.push({ weight: rep * per, color: zoneColor(s), lift: zoneLift(s.zone), title })
        if (rec && i < s.reps - 1) out.push({ weight: rec * per, color: recColor, lift: 0, title })
      }
    } else if (s.kind === 'run_walk' && s.reps) {
      const run = s.run_s ?? 0
      const walk = s.walk_s ?? 0
      const per = total / (s.reps * (run + walk || 1))
      for (let i = 0; i < s.reps; i++) {
        out.push({ weight: run * per, color: zoneColor(s), lift: zoneLift(s.zone), title })
        if (walk && i < s.reps - 1) out.push({ weight: walk * per, color: WALK_COLOR, lift: 0, title })
      }
    } else {
      out.push({ weight: total, color: zoneColor(s), lift: zoneLift(s.zone), title })
    }
  }
  return out
})

function amount(s: ResolvedSegment): string {
  switch (s.kind) {
    case 'intervals': {
      const len = s.distance_m ? `${s.distance_m} ${t('plan.unit.m')}` : fmtSeconds(s.duration_s ?? 0, minU(), secU())
      const rec = s.recovery ? `, ${t('plan.seg.rest')} ${rec2(s)}` : ''
      return `${s.reps} × ${len}${rec}`
    }
    case 'run_walk':
      return `${s.reps} × (${t('plan.seg.runShort')} ${fmtSeconds(s.run_s ?? 0, minU(), secU())}, ${t('plan.seg.walkShort')} ${fmtSeconds(s.walk_s ?? 0, minU(), secU())})`
    case 'walk':
      return `${s.duration_min} ${minU()}`
    default:
      return s.distance_km != null && !s.duration_min
        ? `${s.distance_km} ${km()}`
        : s.distance_km != null
          ? `${Math.round(s.distance_km * 10) / 10} ${km()}`
          : `${s.duration_min} ${minU()}`
  }
}

function rec2(s: ResolvedSegment): string {
  const r = s.recovery!
  return r.distance_m ? `${r.distance_m} ${t('plan.unit.m')}` : fmtSeconds(r.duration_s ?? 0, minU(), secU())
}

function paceText(s: ResolvedSegment): string | null {
  const r = fmtRange(s.pace)
  return r ? `${r}/${km()}` : null
}
</script>

<style scoped>
.ws { margin-top: 10px; }
/* Высота блока — интенсивность: базовая у лёгких/длинных/пауз, темп +1px, интервалы +2px. */
.ws { --ws-h: 10px; }
.ws--compact { --ws-h: 6px; }
.ws-bar { display: flex; align-items: flex-end; gap: 2px; height: calc(var(--ws-h) + 2px); }
.ws-block { display: block; min-width: 3px; height: calc(var(--ws-h) + var(--lift, 0) * 1px); border-radius: 3px; }
.ws-legend { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 6px; }
.ws-item {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 1px 10px;
  font-size: 0.78rem; line-height: 1.4;
}
.ws-dot { width: 8px; height: 8px; border-radius: 50%; align-self: center; flex: none; }
.ws-name { font-weight: 700; color: var(--text); min-width: 96px; }
.ws-amount, .ws-pace, .ws-hr { color: var(--text-2); }
.ws-pace { font-variant-numeric: tabular-nums; }
.ws-feel { color: var(--text-3); font-style: italic; }
.ws-hr { color: var(--text-3); }
.ws-hr i { color: var(--red); font-size: 0.68rem; margin-right: 3px; }
</style>

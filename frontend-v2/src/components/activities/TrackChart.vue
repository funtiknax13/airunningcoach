<template>
  <div class="tchart">
    <div class="tchart-head">
      <span class="tchart-title">{{ title }}</span>
      <span v-if="unit" class="tchart-unit">{{ unit }}</span>
    </div>
    <div v-if="points.length < 2" class="tchart-empty">Недостаточно данных</div>
    <svg v-else :viewBox="`0 0 ${W} ${H}`" class="tchart-svg" preserveAspectRatio="none">
      <line v-for="y in gridYs" :key="y" :x1="padL" :y1="y" :x2="W - padR" :y2="y" stroke="var(--border)" stroke-width="1" />
      <!-- Полосы быстрых сегментов интервалов -->
      <rect v-for="(b, i) in bandRects" :key="i" :x="b.x" :y="padT" :width="b.w" :height="H - padT - padB"
        :fill="bandColor" opacity="0.14" />
      <polygon v-if="fill" :points="areaPoints" :fill="color" opacity="0.12" />
      <polyline :points="linePoints" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    </svg>
    <div v-if="points.length >= 2" class="tchart-labels">
      <span>{{ fmtY(yMax) }}</span>
      <span class="tchart-x">0 {{ distUnit }} — {{ (totalX / 1000).toFixed(1) }} км</span>
      <span>{{ fmtY(yMin) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  unit?: string
  points: { x: number; y: number | null }[] // x — метры от старта
  color: string
  invert?: boolean // меньше = выше на графике (для темпа)
  fill?: boolean
  bands?: { from_m: number; to_m: number }[]
  bandColor?: string
  fmtY?: (v: number) => string
}>(), {
  invert: false,
  fill: true,
  bands: () => [],
  bandColor: 'var(--brand)',
  fmtY: (v: number) => String(Math.round(v)),
})

const W = 800, H = 160, padL = 8, padR = 8, padT = 10, padB = 10
const distUnit = ''

const valid = computed(() => props.points.filter((p) => p.y != null && isFinite(p.y)))
const totalX = computed(() => props.points.length ? props.points[props.points.length - 1].x || 1 : 1)
const yMin = computed(() => {
  const ys = valid.value.map((p) => p.y as number)
  return ys.length ? Math.min(...ys) : 0
})
const yMax = computed(() => {
  const ys = valid.value.map((p) => p.y as number)
  return ys.length ? Math.max(...ys) : 1
})
const yRange = computed(() => {
  const r = yMax.value - yMin.value
  return r > 0 ? r : 1
})

function xPix(x: number) { return padL + (x / totalX.value) * (W - padL - padR) }
function yPix(y: number) {
  let t = (y - yMin.value) / yRange.value
  if (props.invert) t = 1 - t
  return padT + (1 - t) * (H - padT - padB)
}

const linePoints = computed(() =>
  valid.value.map((p) => `${xPix(p.x)},${yPix(p.y as number)}`).join(' ')
)
const areaPoints = computed(() => {
  if (!valid.value.length) return ''
  const base = H - padB
  const first = `${xPix(valid.value[0].x)},${base}`
  const last = `${xPix(valid.value[valid.value.length - 1].x)},${base}`
  return `${first} ${linePoints.value} ${last}`
})
const gridYs = computed(() => [yPix(yMin.value), yPix((yMin.value + yMax.value) / 2), yPix(yMax.value)])

const bandRects = computed(() =>
  props.bands.map((b) => ({ x: xPix(b.from_m), w: Math.max(1, xPix(b.to_m) - xPix(b.from_m)) }))
)
</script>

<style scoped>
.tchart { padding: 4px 0; }
.tchart-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.tchart-title { font-weight: 700; font-size: .88rem; color: var(--text); }
.tchart-unit { font-size: .74rem; color: var(--text-3); }
.tchart-empty { font-size: .82rem; color: var(--text-3); padding: 20px 0; text-align: center; }
.tchart-svg { width: 100%; height: 160px; display: block; }
.tchart-labels { display: flex; justify-content: space-between; font-size: .7rem; color: var(--text-3); margin-top: 2px; }
.tchart-x { flex: 1; text-align: center; }
</style>

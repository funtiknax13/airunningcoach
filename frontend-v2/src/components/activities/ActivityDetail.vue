<template>
  <div class="act-detail">
    <div v-if="loading" class="act-detail-loading">
      <i class="fas fa-spinner fa-spin"></i> Загружаем данные…
    </div>
    <div v-else-if="detail">

      <!-- Доп. метрики -->
      <div class="act-detail-metrics">
        <div v-if="detail.max_heart_rate" class="act-dm">
          <i class="fas fa-heart" style="color:var(--red)"></i>
          <span>{{ detail.max_heart_rate }} <small>макс bpm</small></span>
        </div>
        <div v-if="detail.avg_cadence" class="act-dm">
          <i class="fas fa-shoe-prints" style="color:var(--brand)"></i>
          <span>{{ detail.avg_cadence }} <small>шаг/мин</small></span>
        </div>
        <div v-if="detail.elevation_gain" class="act-dm">
          <i class="fas fa-mountain" style="color:#10b981"></i>
          <span>{{ detail.elevation_gain }} <small>м ↑</small></span>
        </div>
        <div v-if="detail.calories" class="act-dm">
          <i class="fas fa-fire" style="color:#f59e0b"></i>
          <span>{{ detail.calories }} <small>ккал</small></span>
        </div>
      </div>

      <!-- График темпа -->
      <div v-if="chartSplits.length > 1" class="act-detail-section">
        <div class="act-detail-label"><i class="fas fa-chart-line"></i> Темп по км</div>
        <div class="pace-chart-wrap">
          <svg :viewBox="`0 0 ${svgW} ${svgH}`" class="pace-chart" preserveAspectRatio="none">
            <!-- Сетка -->
            <line v-for="y in gridYs" :key="y"
              :x1="pad" :y1="y" :x2="svgW - pad/2" :y2="y"
              stroke="var(--border)" stroke-width="1" />
            <!-- Линия темпа -->
            <polyline :points="pacePoints" fill="none"
              stroke="var(--brand)" stroke-width="2" stroke-linejoin="round" />
            <!-- Зоны HR (если есть) -->
            <circle v-for="(s, i) in chartSplits" :key="i"
              :cx="xScale(i)" :cy="yScale(s.pace!)"
              r="3" fill="var(--brand)" />
          </svg>
          <!-- Y-метки -->
          <div class="pace-y-labels">
            <span v-for="l in yLabels" :key="l" class="pace-y-lbl">{{ l }}</span>
          </div>
          <!-- X-метки -->
          <div class="pace-x-labels">
            <span v-for="(s, i) in chartSplits" :key="i" class="pace-x-lbl">{{ s.km }}</span>
          </div>
        </div>
      </div>

      <!-- Таблица сплитов -->
      <div v-if="detail.splits?.length" class="act-detail-section">
        <div class="act-detail-label"><i class="fas fa-stopwatch"></i> Сплиты</div>
        <table class="splits-table">
          <thead>
            <tr>
              <th>Км</th>
              <th>Темп</th>
              <th v-if="hasSplitHR">♥ bpm</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in detail.splits" :key="s.km" :class="splitClass(s)">
              <td>{{ s.km }}</td>
              <td>{{ s.pace ? fmtPace(s.pace) : '—' }}</td>
              <td v-if="hasSplitHR">{{ s.avg_hr ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Таблица кругов -->
      <div v-if="detail.laps?.length" class="act-detail-section">
        <div class="act-detail-label"><i class="fas fa-rotate"></i> Круги</div>
        <table class="splits-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Дист.</th>
              <th>Темп</th>
              <th v-if="hasLapHR">♥ avg</th>
              <th v-if="hasLapHR">♥ max</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in detail.laps" :key="l.num">
              <td>{{ l.num }}</td>
              <td>{{ l.dist_km }} км</td>
              <td>{{ l.pace ? fmtPace(l.pace) : '—' }}</td>
              <td v-if="hasLapHR">{{ l.avg_hr ?? '—' }}</td>
              <td v-if="hasLapHR">{{ l.max_hr ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Заметки -->
      <div v-if="detail.notes" class="act-detail-section">
        <div class="act-detail-label"><i class="fas fa-note-sticky"></i> Заметки</div>
        <p class="act-detail-notes">{{ detail.notes }}</p>
      </div>

      <div v-if="!hasAnyDetail" class="act-detail-empty">
        Детальные данные отсутствуют. Импортируйте пробежку через GPX или FIT для полной статистики.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { activitiesApi } from '@/api'
import type { ActivityDetail, ActivitySplit } from '@/api/types'

const props = defineProps<{ activityId: number }>()

const detail  = ref<ActivityDetail | null>(null)
const loading = ref(false)

onMounted(load)
watch(() => props.activityId, load)

async function load() {
  loading.value = true
  try { detail.value = await activitiesApi.detail(props.activityId) }
  finally { loading.value = false }
}

function fmtPace(p: number) {
  const m = Math.floor(p); const s = Math.round((p - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const hasAnyDetail = computed(() =>
  detail.value && (
    detail.value.laps?.length ||
    detail.value.splits?.length ||
    detail.value.max_heart_rate ||
    detail.value.elevation_gain ||
    detail.value.notes
  )
)
const hasSplitHR = computed(() => detail.value?.splits?.some(s => s.avg_hr))
const hasLapHR   = computed(() => detail.value?.laps?.some(l => l.avg_hr))

// ── SVG chart ────────────────────────────────────────────────────────────────
const svgW = 400, svgH = 80, pad = 24

const chartSplits = computed<ActivitySplit[]>(() =>
  (detail.value?.splits || []).filter(s => s.pace !== null)
)

const paceMin = computed(() => Math.min(...chartSplits.value.map(s => s.pace!)))
const paceMax = computed(() => Math.max(...chartSplits.value.map(s => s.pace!)))

// Pace is inverted: faster (lower value) = higher on chart
function xScale(i: number) {
  const n = chartSplits.value.length
  return pad + (i / Math.max(n - 1, 1)) * (svgW - pad * 1.5)
}
function yScale(pace: number) {
  const range = paceMax.value - paceMin.value || 0.5
  return pad / 2 + ((pace - paceMin.value) / range) * (svgH - pad)
}

const pacePoints = computed(() =>
  chartSplits.value.map((s, i) => `${xScale(i)},${yScale(s.pace!)}`).join(' ')
)

const gridYs = computed(() => {
  const mid = (paceMin.value + paceMax.value) / 2
  return [paceMin.value, mid, paceMax.value].map(p => yScale(p))
})
const yLabels = computed(() => {
  const mid = (paceMin.value + paceMax.value) / 2
  return [paceMax.value, mid, paceMin.value].map(p => fmtPace(p))
})

// Подсветка самого быстрого/медленного км
function splitClass(s: ActivitySplit) {
  if (!s.pace || chartSplits.value.length < 2) return ''
  if (s.pace === paceMin.value) return 'split-fast'
  if (s.pace === paceMax.value) return 'split-slow'
  return ''
}
</script>

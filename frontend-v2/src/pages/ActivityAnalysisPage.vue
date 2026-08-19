<template>
  <AppLayout :title="ruEn('Тренировка', 'Activity')">
    <template #header-actions>
      <RouterLink :to="`/activities`" class="btn btn-secondary btn-sm">
        <i class="fas fa-arrow-left"></i> {{ ruEn('Назад', 'Back') }}
      </RouterLink>
    </template>

    <div v-if="loading" class="card empty-state"><p>{{ ruEn('Загружаем анализ…', 'Loading analysis…') }}</p></div>
    <div v-else-if="!detail" class="card empty-state"><p>{{ ruEn('Тренировка не найдена', 'Activity not found') }}</p></div>
    <div v-else-if="!detail.track_points?.length" class="card empty-state">
      <p>{{ ruEn('Для этой тренировки нет GPS-трека — детальный анализ недоступен.', 'No GPS track for this activity — detailed analysis is unavailable.') }}</p>
    </div>

    <template v-else>
      <div class="activity-when">{{ startDateTime }}</div>

      <!-- Статистика -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ ruEn('Дистанция', 'Distance') }}</div>
          <div class="stat-val">{{ detail.distance_km.toFixed(2) }} <small>км</small></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ ruEn('Время', 'Time') }}</div>
          <div class="stat-val">{{ fmtDur(detail.duration_min * 60) }}</div>
          <div v-if="analysis && analysis.pauses.count > 0" class="stat-sub">
            {{ ruEn('без остановок', 'moving') }} — {{ fmtDur(detail.duration_min * 60 - analysis.pauses.total_sec) }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ ruEn('Средний темп', 'Avg pace') }}</div>
          <div class="stat-val">{{ fmtPace(detail.pace_min_per_km) }} <small>/км</small></div>
        </div>
        <div v-if="detail.max_heart_rate" class="stat-card">
          <div class="stat-label">{{ ruEn('Пульс', 'Heart rate') }}</div>
          <div class="stat-val">{{ detail.avg_heart_rate ?? '—' }} <small>уд/мин</small></div>
          <div class="stat-sub">{{ ruEn('макс', 'max') }} {{ detail.max_heart_rate }}</div>
        </div>
        <div v-if="detail.elevation_gain" class="stat-card">
          <div class="stat-label">{{ ruEn('Набор высоты', 'Elevation') }}</div>
          <div class="stat-val">+{{ Math.round(detail.elevation_gain) }} <small>м</small></div>
        </div>
        <div v-if="detail.avg_cadence" class="stat-card">
          <div class="stat-label">{{ ruEn('Каденс', 'Cadence') }}</div>
          <div class="stat-val">{{ detail.avg_cadence }} <small>шаг/мин</small></div>
        </div>
        <div v-if="analysis && analysis.pauses.count > 0" class="stat-card">
          <div class="stat-label">{{ ruEn('Паузы', 'Pauses') }}</div>
          <div class="stat-val">{{ analysis.pauses.count }} <small>{{ ruEn('шт.', '') }}</small></div>
          <div class="stat-sub">{{ fmtDur(analysis.pauses.total_sec) }}</div>
        </div>
      </div>

      <!-- Нарратив -->
      <div v-if="narrative" class="card narrative-card">
        <div class="narrative-badge">
          <i class="fas fa-robot"></i> {{ narrative.badge }}
          <span class="type-pill">{{ analysis?.activity_type.type === 'walk' ? ruEn('Ходьба', 'Walk') : ruEn('Бег', 'Run') }}</span>
        </div>
        <p class="narrative-text" v-html="narrative.sentences.join(' ')"></p>
      </div>

      <!-- Карта -->
      <div class="card map-card">
        <div id="analysis-map" ref="mapEl"></div>
      </div>

      <!-- Разбор интервалов -->
      <div v-if="analysis?.intervals" class="card">
        <div class="section-label"><i class="fas fa-rotate"></i> {{ ruEn('Повторы', 'Reps') }}</div>
        <table class="splits-table">
          <thead>
            <tr>
              <th>#</th>
              <th>{{ ruEn('Дист.', 'Dist.') }}</th>
              <th>{{ ruEn('Темп', 'Pace') }}</th>
              <th v-if="hasRepHr">♥</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in analysis.intervals.reps" :key="i">
              <td>{{ i + 1 }}</td>
              <td>{{ Math.round(r.dist_m) }} м</td>
              <td>{{ fmtPace(r.pace_min_km) }}/км</td>
              <td v-if="hasRepHr">{{ r.avg_hr ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="analysis.intervals.recoveries.length" class="rec-note">
          <i class="fas fa-person-walking"></i>
          {{ ruEn('Отдых между повторами', 'Recovery between reps') }}:
          ~{{ Math.round(avgOf(analysis.intervals.recoveries.map(r => r.dist_m))) }} м,
          {{ fmtPace(avgOf(analysis.intervals.recoveries.map(r => r.pace_min_km))) }}/км
        </p>
      </div>

      <!-- Графики -->
      <div class="card">
        <TrackChart title="Темп" unit="мин/км" :points="pacePoints" color="var(--brand)" invert :bands="fastBands" :fmt-y="fmtPace" />
      </div>
      <div v-if="hasEle" class="card">
        <TrackChart title="Высота" unit="м" :points="elePoints" color="#10b981" />
      </div>
      <div v-if="hasHr" class="card">
        <TrackChart title="Пульс" unit="уд/мин" :points="hrPoints" color="var(--red)" :bands="fastBands" />
      </div>
      <div v-if="hasCad" class="card">
        <TrackChart title="Каденс" unit="шаг/мин" :points="cadPoints" color="var(--blue)" :bands="fastBands" />
      </div>

      <!-- Сплиты -->
      <div v-if="detail.splits?.length" class="card">
        <div class="section-label"><i class="fas fa-stopwatch"></i> {{ ruEn('Сплиты по км', 'Km splits') }}</div>
        <table class="splits-table">
          <thead><tr><th>{{ ruEn('Км', 'Km') }}</th><th>{{ ruEn('Темп', 'Pace') }}</th><th v-if="hasSplitHR">♥</th></tr></thead>
          <tbody>
            <tr v-for="s in detail.splits" :key="s.km">
              <td>{{ s.km }}</td>
              <td>{{ s.pace ? fmtPace(s.pace) : '—' }}</td>
              <td v-if="hasSplitHR">{{ s.avg_hr ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import AppLayout from '@/components/layout/AppLayout.vue'
import TrackChart from '@/components/activities/TrackChart.vue'
import { activitiesApi } from '@/api'
import type { ActivityDetail, ActivityAnalysis } from '@/api/types'
import { buildNarrative, fmtPace, fmtDur, type Narrative } from '@/utils/activityNarrative'

const route = useRoute()
const { locale } = useI18n()
const ruEn = (ru: string, en: string) => (locale.value === 'ru' ? ru : en)

const id = Number(route.params.id)
const detail = ref<ActivityDetail | null>(null)
const loading = ref(false)
const mapEl = ref<HTMLElement | null>(null)
let mapInstance: L.Map | null = null

onMounted(load)
async function load() {
  loading.value = true
  try {
    detail.value = await activitiesApi.detail(id)
  } finally {
    loading.value = false
  }
  // loading=false должен успеть отрендериться (переключить v-if на ветку с #analysis-map)
  // ДО renderMap() — иначе mapEl ещё null, а карта так и останется пустой.
  await nextTick()
  renderMap()
}

const startDateTime = computed(() => {
  if (!detail.value?.date) return ''
  const d = new Date(detail.value.date)
  const lang = locale.value === 'ru' ? 'ru-RU' : 'en-US'
  const datePart = d.toLocaleDateString(lang, { weekday: 'long', day: 'numeric', month: 'long' })
  const timePart = d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' })
  return `${datePart[0].toUpperCase()}${datePart.slice(1)} · ${timePart}`
})

const analysis = computed<ActivityAnalysis | null>(() => detail.value?.analysis ?? null)
const narrative = computed<Narrative | null>(() =>
  analysis.value ? buildNarrative(analysis.value, detail.value?.splits ?? null) : null
)

const points = computed(() => detail.value?.track_points ?? [])
const hasEle = computed(() => points.value.some((p) => p.ele != null))
const hasHr = computed(() => points.value.some((p) => p.hr != null))
const hasCad = computed(() => points.value.some((p) => p.cad != null))
const hasSplitHR = computed(() => detail.value?.splits?.some((s) => s.avg_hr))
const hasRepHr = computed(() => analysis.value?.intervals?.reps.some((r) => r.avg_hr != null))

function avgOf(arr: (number | null)[]): number {
  const v = arr.filter((x): x is number => x != null)
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0
}

// ── Данные графиков: x — метры от старта ────────────────────────────────────
const pacePoints = computed(() => {
  const pts = points.value
  const out: { x: number; y: number | null }[] = []
  for (let i = 0; i < pts.length; i++) {
    if (i === 0) { out.push({ x: 0, y: null }); continue }
    const dDistKm = pts[i].dist - pts[i - 1].dist
    const dTsec = (pts[i].t ?? 0) - (pts[i - 1].t ?? 0)
    const pace = dTsec > 0 && dDistKm > 0 ? (dTsec / 60) / dDistKm : null
    out.push({ x: pts[i].dist * 1000, y: pace })
  }
  return out
})
const elePoints = computed(() => points.value.map((p) => ({ x: p.dist * 1000, y: p.ele ?? null })))
const hrPoints = computed(() => points.value.map((p) => ({ x: p.dist * 1000, y: p.hr ?? null })))
const cadPoints = computed(() => points.value.map((p) => ({ x: p.dist * 1000, y: p.cad ?? null })))

const fastBands = computed(() =>
  (analysis.value?.intervals?.segments ?? []).filter((s) => s.cls === 'fast').map((s) => ({ from_m: s.from_m, to_m: s.to_m }))
)

// ── Карта: полилиния, окрашенная по относительному темпу ────────────────────
function renderMap() {
  if (!mapEl.value || !points.value.length) return
  if (mapInstance) { mapInstance.remove(); mapInstance = null }

  mapInstance = L.map(mapEl.value, { zoomControl: true, attributionControl: true })
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    maxZoom: 20, subdomains: 'abcd',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(mapInstance)

  const pts = points.value
  const paces: number[] = []
  const segPaces: (number | null)[] = [null]
  for (let i = 1; i < pts.length; i++) {
    const dDistKm = pts[i].dist - pts[i - 1].dist
    const dTsec = (pts[i].t ?? 0) - (pts[i - 1].t ?? 0)
    const pace = dTsec > 0 && dDistKm > 0 ? (dTsec / 60) / dDistKm : null
    segPaces.push(pace)
    if (pace != null) paces.push(pace)
  }
  paces.sort((a, b) => a - b)
  const quantile = (q: number) => (paces.length ? paces[Math.min(paces.length - 1, Math.floor(q * paces.length))] : 0)
  const q20 = quantile(0.2), q40 = quantile(0.4), q60 = quantile(0.6), q80 = quantile(0.8)
  const ramp = ['#C2440E', '#F85C1E', '#F8834B', '#FBB489', '#FDE4D3'] // тёмный (быстро) → светлый (медленно)
  const bucketColor = (p: number | null) => {
    if (p == null) return ramp[2]
    if (p <= q20) return ramp[0]; if (p <= q40) return ramp[1]; if (p <= q60) return ramp[2]; if (p <= q80) return ramp[3]
    return ramp[4]
  }

  const bounds: L.LatLngExpression[] = []
  for (let i = 1; i < pts.length; i++) {
    const seg: L.LatLngExpression[] = [[pts[i - 1].lat, pts[i - 1].lon], [pts[i].lat, pts[i].lon]]
    L.polyline(seg, { color: bucketColor(segPaces[i]), weight: 4, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }).addTo(mapInstance!)
    bounds.push(seg[0], seg[1])
  }

  if (bounds.length) {
    L.circleMarker([pts[0].lat, pts[0].lon], { radius: 7, color: '#fff', weight: 2, fillColor: '#16A34A', fillOpacity: 1 })
      .addTo(mapInstance).bindTooltip(ruEn('Старт', 'Start'))
    L.circleMarker([pts[pts.length - 1].lat, pts[pts.length - 1].lon], { radius: 7, color: '#fff', weight: 2, fillColor: '#DC2626', fillOpacity: 1 })
      .addTo(mapInstance).bindTooltip(ruEn('Финиш', 'Finish'))
    mapInstance.fitBounds(bounds as L.LatLngBoundsExpression, { padding: [24, 24] })
  }
  setTimeout(() => mapInstance?.invalidateSize(), 60)
}

watch(() => route.params.id, load)
</script>

<style scoped>
.activity-when { font-size: .84rem; font-weight: 600; color: var(--text-2); margin-bottom: 10px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 16px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 14px 16px; }
.stat-label { font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--text-3); margin-bottom: 4px; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: var(--text); }
.stat-val small { font-size: .8rem; font-weight: 600; color: var(--text-2); }
.stat-sub { font-size: .74rem; color: var(--text-3); margin-top: 2px; }

.narrative-card { display: flex; flex-direction: column; gap: 8px; }
.narrative-badge { display: inline-flex; align-items: center; gap: 8px; font-size: .78rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .04em; color: var(--brand); }
.type-pill { margin-left: 4px; font-size: .68rem; font-weight: 700; text-transform: none; color: var(--text-2);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 99px; padding: 2px 9px; }
.narrative-text { font-size: .92rem; line-height: 1.65; color: var(--text-2); }
.narrative-text :deep(strong) { color: var(--text); }

.map-card { position: relative; z-index: 0; padding: 0; overflow: hidden; }
#analysis-map { height: 340px; width: 100%; }

.section-label { font-weight: 700; font-size: .88rem; color: var(--text); margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
.splits-table { width: 100%; border-collapse: collapse; font-size: .84rem; }
.splits-table th { text-align: left; font-size: .68rem; text-transform: uppercase; color: var(--text-3); padding: 4px 8px; }
.splits-table td { padding: 6px 8px; border-top: 1px solid var(--border); color: var(--text-2); }
.rec-note { margin-top: 10px; font-size: .82rem; color: var(--text-3); }
.empty-state { text-align: center; padding: 40px 0; color: var(--text-2); }
</style>

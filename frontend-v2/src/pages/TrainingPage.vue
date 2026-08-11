<template>
  <AppLayout>
    <!-- Панель: выбор горизонта + генерация -->
    <div class="card plan-toolbar">
      <div class="horizon-seg" role="tablist">
        <button v-for="opt in horizons" :key="opt.weeks" class="hseg"
          :class="{ active: selectedWeeks === opt.weeks, locked: opt.locked }"
          @click="pickHorizon(opt)">
          <i v-if="opt.locked" class="fas fa-crown hseg-crown"></i>
          {{ opt.label }}
        </button>
      </div>
      <button class="btn btn-primary plan-gen" :disabled="store.loading || store.generating" @click="onGenerate">
        <i :class="(store.loading || store.generating) ? 'fas fa-spinner fa-spin' : 'fas fa-wand-magic-sparkles'"></i>
        {{ store.generating ? t('plan.horizon.preparing') : store.loading ? t('plan.generating') : t('plan.generate') }}
      </button>
    </div>

    <div v-if="store.generating" class="plan-preparing">
      <i class="fas fa-spinner fa-spin"></i>
      <span>{{ t('plan.horizon.preparingNote') }}</span>
    </div>

    <!-- Календарь -->
    <div class="card cal">
      <div class="cal-head">
        <button class="cal-nav" @click="shiftMonth(-1)" :aria-label="t('plan.calendar.prev')">
          <i class="fas fa-chevron-left"></i>
        </button>
        <div class="cal-title">{{ monthLabel }}</div>
        <button class="cal-nav" @click="shiftMonth(1)" :aria-label="t('plan.calendar.next')">
          <i class="fas fa-chevron-right"></i>
        </button>
        <button class="cal-today" @click="goToday">{{ t('plan.calendar.today') }}</button>
      </div>

      <div class="cal-grid cal-wd-row">
        <div v-for="wd in weekdayLabels" :key="wd" class="cal-wd">{{ wd }}</div>
      </div>

      <SkeletonLoader v-if="store.loadingPlan && !store.all.length" type="workout-list" :count="6" />
      <div v-else class="cal-grid">
        <button v-for="cell in cells" :key="cell.key" class="cal-cell"
          :class="[
            cell.workout ? typeClass(cell.workout.workout_type) : '',
            {
              'is-out': !cell.inMonth,
              'is-today': cell.isToday,
              'is-past': cell.isPast,
              'is-selected': cell.key === selectedKey,
              'has-workout': !!cell.workout,
              'is-done': cell.workout && isDone(cell.workout),
            },
          ]"
          @click="selectDay(cell)">
          <span class="cal-num">{{ cell.date.getDate() }}</span>
          <template v-if="cell.workout">
            <span class="cal-dot"></span>
            <span class="cal-chip">
              {{ t(`plan.type.${cell.workout.workout_type}`) }}<template v-if="cell.workout.distance_km"> · {{ cell.workout.distance_km }}</template>
            </span>
            <i v-if="isDone(cell.workout)" class="fas fa-check cal-check"></i>
          </template>
        </button>
      </div>

      <div class="cal-legend">
        <span v-for="lg in legend" :key="lg.type" class="lg-item">
          <span class="lg-dot" :class="typeClass(lg.type)"></span>{{ lg.label }}
        </span>
      </div>
    </div>

    <!-- Детали выбранного дня -->
    <div v-if="selectedKey" class="card day-detail">
      <div class="dd-head">
        <div class="dd-date">
          <span class="dd-daynum">{{ selectedDate?.getDate() }}</span>
          <span class="dd-mon">{{ selectedDate ? monthShort(selectedDate) : '' }}</span>
          <span class="dd-dow">{{ selectedDate ? fullDow(selectedDate) : '' }}</span>
        </div>
        <button class="dd-close" @click="selectedKey = null" :aria-label="t('btn.cancel')">
          <i class="fas fa-xmark"></i>
        </button>
      </div>

      <template v-if="selectedWorkout">
        <span class="workout-type-badge" :class="`badge-type-${selectedWorkout.workout_type}`">
          {{ t(`plan.type.${selectedWorkout.workout_type}`) }}
        </span>
        <p class="dd-desc">{{ selectedWorkout.description }}</p>
        <div class="dd-chips">
          <span v-if="selectedWorkout.distance_km" class="workout-chip">📏 {{ selectedWorkout.distance_km }} km</span>
          <span v-if="selectedWorkout.target_pace_min_km" class="workout-chip">⏱ {{ formatPace(selectedWorkout.target_pace_min_km) }}/km</span>
        </div>

        <div class="dd-action">
          <span v-if="isRest(selectedWorkout.workout_type)" class="badge badge-rest">
            <i class="fas fa-moon"></i> {{ t('plan.status.restDay') }}
          </span>
          <template v-else-if="isDone(selectedWorkout)">
            <span class="badge" :class="selectedWorkout.completion_status === 'completed' ? 'badge-done' : 'badge-approx'">
              {{ selectedWorkout.completion_status === 'completed' ? t('plan.status.done') : t('plan.status.approx') }}
            </span>
            <button class="btn-uncomplete" @click="uncomplete(selectedWorkout.id)" :title="t('plan.status.undoTitle')">
              <i class="fas fa-rotate-left"></i>
            </button>
          </template>
          <template v-else-if="selectedWorkout.completion_status === 'unconfirmed'">
            <span class="badge badge-unconfirmed">{{ t('plan.status.unconfirmed') }}</span>
            <button class="btn-complete" @click="complete(selectedWorkout.id)">
              <i class="fas fa-rotate-right"></i> {{ t('plan.status.retry') }}
            </button>
          </template>
          <button v-else-if="isFuture(selectedWorkout)" class="btn-complete btn-complete--future" disabled :title="t('plan.status.futureTitle')">
            <i class="fas fa-lock"></i> {{ t('plan.status.mark') }}
          </button>
          <button v-else class="btn-complete" @click="complete(selectedWorkout.id)">
            <i class="fas fa-check"></i> {{ t('plan.status.mark') }}
          </button>
        </div>
      </template>
      <p v-else class="dd-empty">{{ t('plan.calendar.noWorkout') }}</p>
    </div>

    <!-- Пустое состояние: плана ещё нет -->
    <div v-if="!store.all.length && !store.loadingPlan" class="card empty-state" style="padding:32px 0">
      <i class="fas fa-calendar-week"></i>
      <p>{{ t('plan.empty') }}</p>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import { useTrainingStore } from '@/stores/training'
import { useAuthStore } from '@/stores/auth'
import { useDialog } from '@/composables/useDialog'
import type { Workout, WorkoutType } from '@/api/types'

const { t, locale } = useI18n()
const store  = useTrainingStore()
const auth   = useAuthStore()
const router = useRouter()
const { prompt, confirm } = useDialog()

onMounted(() => { store.load(); store.refreshStatus() })

// Длинный план собирается в фоне: когда генерация завершилась — прыгаем на
// текущий месяц (план стартует с сегодня) и убираем выбранный день.
watch(() => store.generating, (now, was) => {
  if (was && !now) { goToday(); selectedKey.value = null }
})

// ── Премиум ───────────────────────────────────────────────────────────────
const isPremium = computed(() => {
  if (!auth.user?.is_premium) return false
  if (!auth.user.premium_until) return true
  return new Date(auth.user.premium_until) > new Date()
})

// ── Горизонты ─────────────────────────────────────────────────────────────
const selectedWeeks = ref(1)
const horizons = computed(() => [
  { weeks: 1, label: t('plan.horizon.week'),  locked: false },
  { weeks: 4, label: t('plan.horizon.month'), locked: !isPremium.value },
])

async function pickHorizon(opt: { weeks: number; locked: boolean }) {
  if (opt.locked) {
    const go = await confirm(t('plan.horizon.premiumUpsell'), {
      confirmLabel: t('plan.horizon.getPremium'), cancelLabel: t('btn.cancel'),
    })
    if (go) router.push('/subscription')
    return
  }
  selectedWeeks.value = opt.weeks
}

async function onGenerate() {
  try {
    await store.generate(selectedWeeks.value)
    // Неделя готова сразу; длинный план — в фоне (goToday сработает по watch,
    // когда store.generating погаснет).
    if (!store.generating) { goToday(); selectedKey.value = null }
  } catch (e: any) {
    // На всякий случай (клиентский гейт должен был не пустить): 403 от бэкенда
    if (String(e?.message ?? '').includes('Premium') || e?.status === 403) {
      const go = await confirm(t('plan.horizon.premiumUpsell'), {
        confirmLabel: t('plan.horizon.getPremium'), cancelLabel: t('btn.cancel'),
      })
      if (go) router.push('/subscription')
    }
  }
}

// ── Дата-хелперы ──────────────────────────────────────────────────────────
const RUNNING: WorkoutType[] = ['easy', 'tempo', 'interval', 'long', 'recovery']
const MON_RU = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
const MON_RU_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
const MON_EN = ['January','February','March','April','May','June','July','August','September','October','November','December']
const MON_EN_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const DOW_RU = ['воскресенье','понедельник','вторник','среда','четверг','пятница','суббота']
const DOW_EN = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']

function keyOf(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const today = new Date(); today.setHours(0, 0, 0, 0)
const todayKey = keyOf(today)

const weekdayLabels = computed(() =>
  locale.value === 'ru' ? ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'] : ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])

// Тренировки по дате (одна на день)
const byDate = computed(() => {
  const m = new Map<string, Workout>()
  for (const w of store.all) {
    if (!w.planned_date) continue
    m.set(keyOf(new Date(w.planned_date)), w)
  }
  return m
})

// ── Навигация по месяцам ──────────────────────────────────────────────────
const viewMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))
function shiftMonth(delta: number) {
  viewMonth.value = new Date(viewMonth.value.getFullYear(), viewMonth.value.getMonth() + delta, 1)
}
function goToday() { viewMonth.value = new Date(today.getFullYear(), today.getMonth(), 1) }

const monthLabel = computed(() => {
  const m = viewMonth.value.getMonth(); const y = viewMonth.value.getFullYear()
  return `${(locale.value === 'ru' ? MON_RU : MON_EN)[m]} ${y}`
})

interface Cell { date: Date; key: string; inMonth: boolean; isToday: boolean; isPast: boolean; workout: Workout | null }
const cells = computed<Cell[]>(() => {
  const y = viewMonth.value.getFullYear(); const m = viewMonth.value.getMonth()
  const first = new Date(y, m, 1)
  const dow = (first.getDay() + 6) % 7            // 0 = понедельник
  const start = new Date(y, m, 1 - dow)
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const rows = Math.ceil((dow + daysInMonth) / 7)
  const out: Cell[] = []
  const cur = new Date(start)
  for (let i = 0; i < rows * 7; i++) {
    const d = new Date(cur); d.setHours(0, 0, 0, 0)
    const key = keyOf(d)
    out.push({
      date: d, key,
      inMonth: d.getMonth() === m,
      isToday: key === todayKey,
      isPast: d < today,
      workout: byDate.value.get(key) ?? null,
    })
    cur.setDate(cur.getDate() + 1)
  }
  return out
})

// ── Выбранный день ────────────────────────────────────────────────────────
const selectedKey = ref<string | null>(null)
const selectedDate = computed(() => {
  if (!selectedKey.value) return null
  const [y, m, d] = selectedKey.value.split('-').map(Number)
  return new Date(y, m - 1, d)
})
const selectedWorkout = computed(() => selectedKey.value ? byDate.value.get(selectedKey.value) ?? null : null)
function selectDay(cell: Cell) { selectedKey.value = cell.key }

// ── Форматирование ────────────────────────────────────────────────────────
const legend = computed(() => (['easy','tempo','interval','long','rest'] as WorkoutType[])
  .map(type => ({ type, label: t(`plan.type.${type}`) })))
function typeClass(type: WorkoutType) { return `t-${type}` }
function isRest(type: WorkoutType) { return !RUNNING.includes(type) }
function isDone(w: Workout) { return w.completion_status === 'completed' || w.completion_status === 'approximate' }
function isFuture(w: Workout) {
  if (!w.planned_date) return false
  const d = new Date(w.planned_date); d.setHours(0, 0, 0, 0)
  return d > today
}
function monthShort(d: Date) { return (locale.value === 'ru' ? MON_RU_SHORT : MON_EN_SHORT)[d.getMonth()] }
function fullDow(d: Date) { return (locale.value === 'ru' ? DOW_RU : DOW_EN)[d.getDay()] }
function formatPace(p: number) { const m = Math.floor(p); const s = Math.round((p - m) * 60); return `${m}:${String(s).padStart(2, '0')}` }

// ── Действия ──────────────────────────────────────────────────────────────
async function complete(id: number) {
  const notes = await prompt(t('plan.workout.notes'), {
    placeholder: t('plan.workout.notesPlaceholder'),
    confirmLabel: t('plan.status.mark'), cancelLabel: t('btn.cancel'),
  })
  if (notes === null) return
  await store.completeWorkout(id, notes || undefined)
}
async function uncomplete(id: number) {
  const ok = await confirm(t('plan.status.undoConfirm'), {
    cancelLabel: t('btn.cancel'), confirmLabel: t('plan.status.undoBtn'),
  })
  if (!ok) return
  await store.uncompleteWorkout(id)
}
</script>

<style scoped>
/* ── Панель горизонта ── */
.plan-toolbar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin-bottom: 16px;
}
.horizon-seg {
  display: inline-flex; background: var(--surface-3); border-radius: 10px; padding: 3px; gap: 2px;
}
.hseg {
  border: none; background: none; cursor: pointer; padding: 7px 14px; border-radius: 8px;
  font-size: 0.86rem; font-weight: 600; color: var(--text-2); white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px; transition: background .15s, color .15s;
}
.hseg.active { background: var(--surface); color: var(--text); box-shadow: var(--shadow-sm); }
.hseg.locked { color: var(--text-3); }
.hseg-crown { font-size: 0.72rem; color: var(--brand); }
.plan-gen { margin-left: auto; }
.plan-preparing {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
  padding: 12px 16px; border-radius: 10px; font-size: 0.88rem; color: var(--text-2);
  background: rgba(248, 92, 30, 0.08);
  border: 1px solid color-mix(in srgb, var(--brand) 25%, var(--border));
}
.plan-preparing i { color: var(--brand); }

/* ── Календарь ── */
.cal { margin-bottom: 16px; }
.cal-head { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.cal-title { font-size: 1.02rem; font-weight: 700; min-width: 150px; text-align: center; }
.cal-nav {
  width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text-2); cursor: pointer; flex: none;
}
.cal-nav:hover { background: var(--surface-2); color: var(--text); }
.cal-today {
  margin-left: auto; border: 1px solid var(--border); background: var(--surface);
  color: var(--text-2); border-radius: 8px; padding: 7px 12px; font-size: 0.8rem;
  font-weight: 600; cursor: pointer;
}
.cal-today:hover { background: var(--surface-2); color: var(--text); }

.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
.cal-wd-row { margin-bottom: 6px; }
.cal-wd { text-align: center; font-size: 0.72rem; font-weight: 700; color: var(--text-3); text-transform: uppercase; }

.cal-cell {
  position: relative; min-height: 74px; border: 1px solid var(--border); background: var(--surface);
  border-radius: 10px; padding: 6px; cursor: pointer; text-align: left;
  display: flex; flex-direction: column; gap: 4px; overflow: hidden;
  transition: border-color .12s, box-shadow .12s, transform .06s;
}
.cal-cell:hover { border-color: var(--border-2); }
.cal-cell:active { transform: scale(0.98); }
.cal-cell.is-out { opacity: 0.38; }
.cal-cell.is-past:not(.is-today) { opacity: 0.66; }
.cal-cell.is-today { border-color: var(--brand); box-shadow: 0 0 0 1px var(--brand) inset; }
.cal-cell.is-selected { box-shadow: 0 0 0 2px var(--brand); border-color: var(--brand); }
.cal-num { font-size: 0.82rem; font-weight: 700; color: var(--text-2); }
.cal-cell.is-today .cal-num { color: var(--brand); }

/* Цвет тренировки в ячейке — по типу (--dot задаётся классом t-*) */
.cal-cell.has-workout { background: var(--dotbg, var(--surface-2)); border-color: color-mix(in srgb, var(--dot, var(--border-2)) 30%, var(--border)); }
.cal-dot { display: none; }
.cal-chip {
  font-size: 0.72rem; font-weight: 600; line-height: 1.15; color: var(--dot, var(--text-2));
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.cal-check { position: absolute; top: 6px; right: 6px; font-size: 0.72rem; color: var(--green); }
.cal-cell.is-done { background: var(--green-dim); border-color: color-mix(in srgb, var(--green) 30%, var(--border)); }
.cal-cell.is-done .cal-chip { color: var(--text-3); text-decoration: line-through; }

/* Палитра типов */
.t-easy     { --dot: var(--green);  --dotbg: var(--green-dim); }
.t-tempo    { --dot: var(--yellow); --dotbg: var(--yellow-dim); }
.t-interval { --dot: var(--red);    --dotbg: var(--red-dim); }
.t-long     { --dot: var(--blue);   --dotbg: var(--blue-dim); }
.t-recovery { --dot: var(--text-3); --dotbg: var(--surface-3); }
.t-rest     { --dot: var(--text-3); --dotbg: var(--surface-3); }

/* Легенда */
.cal-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
.lg-item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; color: var(--text-3); }
.lg-dot { width: 10px; height: 10px; border-radius: 3px; background: var(--dot); }

/* ── Детали дня ── */
.day-detail { margin-bottom: 16px; }
.dd-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.dd-date { display: flex; align-items: baseline; gap: 6px; }
.dd-daynum { font-size: 1.5rem; font-weight: 800; }
.dd-mon { font-size: 0.9rem; color: var(--text-2); }
.dd-dow { font-size: 0.85rem; color: var(--text-3); text-transform: capitalize; }
.dd-close { margin-left: auto; width: 32px; height: 32px; border: none; background: var(--surface-3);
  border-radius: 8px; color: var(--text-2); cursor: pointer; }
.dd-close:hover { background: var(--border); }
.dd-desc { margin: 10px 0; line-height: 1.5; }
.dd-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.dd-action { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.dd-empty { color: var(--text-3); margin: 8px 0; }

/* ── Мобилка: компактные ячейки, чип-текст прячем, показываем точку ── */
@media (max-width: 560px) {
  .cal-grid { gap: 4px; }
  .cal-cell { min-height: 46px; padding: 4px; border-radius: 8px; align-items: center; gap: 3px; }
  .cal-num { font-size: 0.78rem; }
  .cal-chip { display: none; }
  .cal-cell.has-workout .cal-dot { display: block; width: 7px; height: 7px; border-radius: 50%; background: var(--dot); }
  .cal-cell.is-done .cal-dot { background: var(--green); }
  .cal-check { display: none; }
  .cal-cell.is-done { background: var(--green-dim); }
  .cal-title { min-width: 0; font-size: 0.95rem; }
  .plan-gen { margin-left: 0; width: 100%; }
  .horizon-seg { width: 100%; justify-content: space-between; }
  .hseg { flex: 1; justify-content: center; padding: 8px 6px; }
}
</style>

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
            cell.workout ? `s-${statusOf(cell)}` : '',
            {
              'is-out': !cell.inMonth,
              'is-today': cell.isToday,
              'is-selected': cell.key === selectedKey,
              'has-workout': !!cell.workout,
            },
          ]"
          @click="selectDay(cell)">
          <span class="cal-num">{{ cell.date.getDate() }}</span>
          <template v-if="cell.workout">
            <i class="cal-ico fas" :class="disciplineIcon(cell.workout)"></i>
            <span class="cal-label">{{ dayLabel(cell.workout)
              }}<template v-if="cell.workout.distance_km"> · {{ cell.workout.distance_km }}</template></span>
            <i v-if="statusOf(cell) === 'done'" class="cal-mark fas fa-check"></i>
            <i v-else-if="statusOf(cell) === 'missed'" class="cal-mark cal-mark--miss fas fa-xmark"></i>
          </template>
        </button>
      </div>

      <div class="cal-legend">
        <span v-for="s in statusLegend" :key="s.cls" class="lg-item">
          <span class="lg-sw" :class="s.cls"></span>{{ s.label }}
        </span>
        <span class="lg-sep"></span>
        <span v-for="d in discLegend" :key="d.icon" class="lg-item">
          <i class="fas lg-ico" :class="d.icon"></i>{{ d.label }}
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
        <div class="dd-badges">
          <span class="dd-discipline" :class="`t-${selectedWorkout.workout_type}`">
            <i class="fas" :class="disciplineIcon(selectedWorkout)"></i> {{ dayLabel(selectedWorkout) }}
          </span>
          <span class="workout-type-badge" :class="`badge-type-${selectedWorkout.workout_type}`">
            {{ t(`plan.type.${selectedWorkout.workout_type}`) }}
          </span>
          <span v-if="selectedStatus === 'missed'" class="badge badge-missed">{{ t('plan.status.missed') }}</span>
        </div>
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

// ── Дисциплина / тип / статус ─────────────────────────────────────────────
function typeClass(type: WorkoutType) { return `t-${type}` }
function isRest(type: WorkoutType) { return !RUNNING.includes(type) }
function isDone(w: Workout) { return w.completion_status === 'completed' || w.completion_status === 'approximate' }
// Ходьба определяется по описанию (модель пишет «ходьба» для восстановительных/
// коленных дней) — отдельного поля дисциплины в плане нет.
function isWalk(w: Workout) { return /ходьб|walk/i.test(w.description || '') }
function disciplineIcon(w: Workout) {
  if (w.workout_type === 'rest') return 'fa-bed'
  return isWalk(w) ? 'fa-person-walking' : 'fa-person-running'
}
function dayLabel(w: Workout) {
  if (w.workout_type === 'rest') return t('plan.type.rest')
  if (isWalk(w)) return t('plan.discipline.walk')
  return t(`plan.type.${w.workout_type}`)
}
// Статус для цветовой схемы ячейки: выполнено / пропущено / не подтверждено /
// отдых / предстоит. Пропущено = прошедший беговой день, который не отмечен.
function statusFor(w: Workout, isPast: boolean): string {
  if (isDone(w)) return 'done'
  if (w.completion_status === 'unconfirmed') return 'unconfirmed'
  if (isRest(w.workout_type)) return 'rest'
  if (isPast) return 'missed'
  return 'upcoming'
}
function statusOf(cell: Cell) { return cell.workout ? statusFor(cell.workout, cell.isPast) : '' }

const statusLegend = computed(() => [
  { cls: 's-done',        label: t('plan.status.done') },
  { cls: 's-missed',      label: t('plan.status.missed') },
  { cls: 's-unconfirmed', label: t('plan.status.unconfirmed') },
])
const discLegend = computed(() => [
  { icon: 'fa-person-running', label: t('plan.discipline.run') },
  { icon: 'fa-person-walking', label: t('plan.discipline.walk') },
  { icon: 'fa-bed',            label: t('plan.type.rest') },
])
const selectedStatus = computed(() => {
  const w = selectedWorkout.value; const d = selectedDate.value
  if (!w || !d) return ''
  const past = new Date(d.getFullYear(), d.getMonth(), d.getDate()) < today
  return statusFor(w, past)
})

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
.cal-cell.is-out { opacity: 0.4; }
.cal-cell.is-today { border-color: var(--brand); box-shadow: 0 0 0 1px var(--brand) inset; }
.cal-cell.is-selected { box-shadow: 0 0 0 2px var(--brand); border-color: var(--brand); }
.cal-num { font-size: 0.82rem; font-weight: 700; color: var(--text-2); }
.cal-cell.is-today .cal-num { color: var(--brand); }

/* Что за тренировка: иконка дисциплины (бег/ходьба/отдых) + подпись типа.
   Иконка окрашена по типу (--dot из t-*). */
.cal-ico { font-size: 0.92rem; color: var(--dot, var(--text-3)); }
.cal-label {
  font-size: 0.72rem; font-weight: 600; line-height: 1.15; color: var(--text-2);
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.cal-mark { position: absolute; top: 6px; right: 6px; font-size: 0.74rem; color: var(--green); }
.cal-mark--miss { color: var(--red); }

/* Цветовая схема ячейки — по СТАТУСУ (выполнено/пропущено/не подтверждено/отдых/
   предстоит). Тип показывает иконка+подпись, а не фон. Без зачёркивания. */
.cal-cell.s-upcoming    { background: var(--surface); }
.cal-cell.s-rest        { background: var(--surface-2); }
.cal-cell.s-rest .cal-ico, .cal-cell.s-rest .cal-label { color: var(--text-3); }
.cal-cell.s-done        { background: var(--green-dim);  border-color: color-mix(in srgb, var(--green) 35%, var(--border)); }
.cal-cell.s-missed      { background: var(--red-dim);    border-color: color-mix(in srgb, var(--red) 35%, var(--border)); }
.cal-cell.s-unconfirmed { background: var(--yellow-dim); border-color: color-mix(in srgb, var(--yellow) 35%, var(--border)); }
.cal-cell.s-done .cal-ico        { color: var(--green); }
.cal-cell.s-missed .cal-ico      { color: var(--red); }
.cal-cell.s-unconfirmed .cal-ico { color: var(--yellow); }

/* Палитра типов (задаёт --dot для иконки/легенды) */
.t-easy     { --dot: var(--green);  --dotbg: var(--green-dim); }
.t-tempo    { --dot: var(--yellow); --dotbg: var(--yellow-dim); }
.t-interval { --dot: var(--red);    --dotbg: var(--red-dim); }
.t-long     { --dot: var(--blue);   --dotbg: var(--blue-dim); }
.t-recovery { --dot: var(--text-3); --dotbg: var(--surface-3); }
.t-rest     { --dot: var(--text-3); --dotbg: var(--surface-3); }

/* Легенда: цвета = статусы, иконки = дисциплина */
.cal-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
.lg-item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; color: var(--text-3); }
.lg-sw { width: 12px; height: 12px; border-radius: 4px; }
.lg-sw.s-done { background: var(--green-dim); border: 1px solid var(--green); }
.lg-sw.s-missed { background: var(--red-dim); border: 1px solid var(--red); }
.lg-sw.s-unconfirmed { background: var(--yellow-dim); border: 1px solid var(--yellow); }
.lg-ico { color: var(--text-2); width: 14px; text-align: center; }
.lg-sep { width: 1px; height: 14px; background: var(--border); }

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
.dd-badges { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.dd-discipline { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; font-size: 0.92rem; color: var(--dot, var(--text)); }
.badge-missed { background: var(--red-dim); color: var(--red); }
.dd-desc { margin: 10px 0; line-height: 1.5; }
.dd-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.dd-action { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.dd-empty { color: var(--text-3); margin: 8px 0; }

/* ── Мобилка: компактные ячейки. Подпись прячем, оставляем иконку дисциплины
   (бег/ходьба/отдых) + цвет-статус — оба читаются с одного взгляда. ── */
@media (max-width: 560px) {
  .cal-grid { gap: 4px; }
  .cal-cell { min-height: 48px; padding: 4px; border-radius: 8px; align-items: center; gap: 2px; }
  .cal-num { font-size: 0.76rem; }
  .cal-label { display: none; }
  .cal-ico { font-size: 0.82rem; }
  .cal-mark { display: none; }
  .cal-title { min-width: 0; font-size: 0.95rem; }
  .plan-gen { margin-left: 0; width: 100%; }
  .horizon-seg { width: 100%; justify-content: space-between; }
  .hseg { flex: 1; justify-content: center; padding: 8px 6px; }
}
</style>

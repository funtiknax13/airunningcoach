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

    <SkeletonLoader v-if="store.loadingPlan && !store.all.length" type="workout-list" :count="6" />

    <template v-else>
      <!-- Агенда по неделям -->
      <div v-for="wk in weeks" :key="wk.key" class="card wk" :class="{ 'wk--current': wk.isCurrent }">
        <div class="wk-head">
          <div class="wk-title">
            <span class="wk-n">{{ weekTitle(wk.n) }}</span>
            <span v-if="wk.isCurrent" class="wk-badge">{{ ruEn('Текущая', 'This week') }}</span>
            <span class="wk-range">{{ weekRange(wk.start) }}</span>
          </div>
          <div class="wk-meta">
            <span class="wk-vol"><i class="fas fa-route"></i>{{ wk.volumeKm }} {{ ruEn('км', 'km') }}</span>
            <span class="wk-cnt">{{ wk.count }} {{ ruEn('трен.', 'wo.') }}</span>
          </div>
        </div>

        <div v-if="wk.count" class="wk-prog">
          <div class="wk-prog-bar"><span :style="{ width: progPct(wk) + '%' }"></span></div>
          <span class="wk-prog-txt">{{ wk.doneCount }}/{{ wk.count }}</span>
        </div>

        <ul class="agw">
          <li v-for="w in wk.days" :key="w.id" class="agw-row"
            :class="[`t-${w.workout_type}`, `s-${statusOfW(w)}`, { 'is-today': isTodayW(w), 'is-rest': isRest(w.workout_type) }]">
            <div class="agw-date">
              <span class="agw-dow">{{ wdShort(w) }}</span>
              <span class="agw-num">{{ dayNum(w) }}</span>
            </div>
            <div class="agw-ico"><i class="fas" :class="disciplineIcon(w)"></i></div>
            <div class="agw-body">
              <div class="agw-top">
                <span class="agw-label">{{ dayLabel(w) }}</span>
                <span v-if="!isRest(w.workout_type)" class="workout-type-badge" :class="`badge-type-${w.workout_type}`">
                  {{ t(`plan.type.${w.workout_type}`) }}
                </span>
              </div>
              <p v-if="w.description" class="agw-desc">{{ w.description }}</p>
              <div v-if="w.distance_km || w.target_pace_min_km" class="agw-chips">
                <span v-if="w.distance_km" class="workout-chip">📏 {{ w.distance_km }} {{ ruEn('км', 'km') }}</span>
                <span v-if="w.target_pace_min_km" class="workout-chip">⏱ {{ formatPace(w.target_pace_min_km) }}/{{ ruEn('км', 'km') }}</span>
              </div>
            </div>
            <div class="agw-action">
              <span v-if="isRest(w.workout_type)" class="badge badge-rest">
                <i class="fas fa-moon"></i> {{ t('plan.status.restDay') }}
              </span>
              <template v-else-if="isDone(w)">
                <span class="badge" :class="w.completion_status === 'completed' ? 'badge-done' : 'badge-approx'">
                  {{ w.completion_status === 'completed' ? t('plan.status.done') : t('plan.status.approx') }}
                </span>
                <button class="btn-uncomplete" @click="uncomplete(w.id)" :title="t('plan.status.undoTitle')">
                  <i class="fas fa-rotate-left"></i>
                </button>
              </template>
              <template v-else-if="w.completion_status === 'unconfirmed'">
                <span class="badge badge-unconfirmed">{{ t('plan.status.unconfirmed') }}</span>
                <button class="btn-complete" @click="complete(w.id)">
                  <i class="fas fa-rotate-right"></i> {{ t('plan.status.retry') }}
                </button>
              </template>
              <button v-else-if="isFuture(w)" class="btn-complete btn-complete--future" disabled :title="t('plan.status.futureTitle')">
                <i class="fas fa-lock"></i> {{ t('plan.status.mark') }}
              </button>
              <button v-else class="btn-complete" @click="complete(w.id)">
                <i class="fas fa-check"></i> {{ t('plan.status.mark') }}
              </button>
            </div>
          </li>
        </ul>
      </div>

      <!-- Пустые состояния -->
      <div v-if="!store.all.length" class="card empty-state" style="padding:32px 0">
        <i class="fas fa-calendar-week"></i>
        <p>{{ t('plan.empty') }}</p>
      </div>
      <div v-else-if="!weeks.length" class="card empty-state" style="padding:32px 0">
        <i class="fas fa-flag-checkered"></i>
        <p>{{ ruEn('Все тренировки уже позади — сгенерируйте новый план.', 'All workouts are behind you — generate a new plan.') }}</p>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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

const ruEn = (ru: string, en: string) => (locale.value === 'ru' ? ru : en)

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
const MON_RU_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
const MON_EN_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const WD_RU = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
const WD_EN = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

function keyOf(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const today = new Date(); today.setHours(0, 0, 0, 0)
const todayKey = keyOf(today)
function monthShort(d: Date) { return (locale.value === 'ru' ? MON_RU_SHORT : MON_EN_SHORT)[d.getMonth()] }

// Понедельник недели, к которой относится дата
function weekStartOf(d: Date) {
  const x = new Date(d); x.setHours(0, 0, 0, 0)
  const dow = (x.getDay() + 6) % 7          // 0 = понедельник
  x.setDate(x.getDate() - dow)
  return x
}
const currentWeekStart = weekStartOf(today)
const currentWeekKey = keyOf(currentWeekStart)

// ── Недели (агенда): текущая и будущие. Прошедшие недели скрываем — план
// смотрит вперёд, «что делать сейчас и дальше». ──────────────────────────
interface Week {
  key: string; n: number; start: Date; isCurrent: boolean;
  days: Workout[]; count: number; doneCount: number; volumeKm: number;
}
const weeks = computed<Week[]>(() => {
  const map = new Map<string, Workout[]>()
  for (const w of store.all) {
    if (!w.planned_date) continue
    const d = new Date(w.planned_date); d.setHours(0, 0, 0, 0)
    const wk = keyOf(weekStartOf(d))
    if (wk < currentWeekKey) continue        // прошлые недели скрываем
    if (!map.has(wk)) map.set(wk, [])
    map.get(wk)!.push(w)
  }
  return [...map.keys()].sort().map((k, i) => {
    const days = map.get(k)!.slice().sort((a, b) => (a.planned_date! < b.planned_date! ? -1 : 1))
    const running = days.filter(w => !isRest(w.workout_type))
    const volumeKm = running.reduce((s, w) => s + (w.distance_km || 0), 0)
    const [y, m, dd] = k.split('-').map(Number)
    return {
      key: k, n: i + 1, start: new Date(y, m - 1, dd), isCurrent: k === currentWeekKey,
      days, count: running.length, doneCount: running.filter(isDone).length,
      volumeKm: Math.round(volumeKm * 10) / 10,
    }
  })
})

function weekTitle(n: number) { return ruEn(`Неделя ${n}`, `Week ${n}`) }
function weekRange(start: Date) {
  const end = new Date(start); end.setDate(end.getDate() + 6)
  return start.getMonth() === end.getMonth()
    ? `${start.getDate()}–${end.getDate()} ${monthShort(end)}`
    : `${start.getDate()} ${monthShort(start)} – ${end.getDate()} ${monthShort(end)}`
}
function progPct(wk: Week) { return wk.count ? Math.round((wk.doneCount / wk.count) * 100) : 0 }

function wdShort(w: Workout) {
  const d = new Date(w.planned_date!); const idx = (d.getDay() + 6) % 7
  return (locale.value === 'ru' ? WD_RU : WD_EN)[idx]
}
function dayNum(w: Workout) { return new Date(w.planned_date!).getDate() }
function isTodayW(w: Workout) {
  const d = new Date(w.planned_date!); d.setHours(0, 0, 0, 0)
  return keyOf(d) === todayKey
}
function isPastW(w: Workout) {
  const d = new Date(w.planned_date!); d.setHours(0, 0, 0, 0)
  return d < today
}

// ── Дисциплина / тип / статус ─────────────────────────────────────────────
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
// Статус: выполнено / пропущено / не подтверждено / отдых / предстоит.
// Пропущено = прошедший беговой день, который не отмечен.
function statusFor(w: Workout, isPast: boolean): string {
  if (isDone(w)) return 'done'
  if (w.completion_status === 'unconfirmed') return 'unconfirmed'
  if (isRest(w.workout_type)) return 'rest'
  if (isPast) return 'missed'
  return 'upcoming'
}
function statusOfW(w: Workout) { return statusFor(w, isPastW(w)) }

function isFuture(w: Workout) {
  if (!w.planned_date) return false
  const d = new Date(w.planned_date); d.setHours(0, 0, 0, 0)
  return d > today
}
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

/* ── Неделя-карточка ── */
.wk { margin-bottom: 14px; }
.wk--current { border-color: color-mix(in srgb, var(--brand) 45%, var(--border)); }
.wk-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.wk-title { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.wk-n { font-size: 1.05rem; font-weight: 800; letter-spacing: -0.01em; }
.wk-badge {
  font-size: 0.66rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  color: var(--brand); background: var(--brand-light); padding: 2px 8px; border-radius: 99px;
}
.wk-range { font-size: 0.82rem; color: var(--text-3); }
.wk-meta { display: flex; align-items: center; gap: 12px; font-size: 0.82rem; color: var(--text-2); }
.wk-vol { font-weight: 700; }
.wk-vol i { color: var(--brand); margin-right: 5px; }
.wk-cnt { color: var(--text-3); }

.wk-prog { display: flex; align-items: center; gap: 10px; margin: 12px 0 2px; }
.wk-prog-bar { flex: 1; height: 6px; border-radius: 99px; background: var(--surface-3); overflow: hidden; }
.wk-prog-bar span { display: block; height: 100%; background: var(--green); border-radius: 99px; transition: width .3s; }
.wk-prog-txt { font-size: 0.76rem; font-weight: 700; color: var(--text-3); min-width: 32px; text-align: right; }

/* ── Список дней ── */
.agw { list-style: none; margin: 12px 0 0; padding: 0; }
.agw-row { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; border-top: 1px solid var(--border); }
.agw-row:first-child { border-top: none; }
.agw-row.is-today {
  margin: 4px -10px; padding: 12px 10px; border-radius: 12px;
  background: var(--brand-light); border-top-color: transparent;
}

.agw-date { flex: none; width: 40px; text-align: center; padding-top: 2px; }
.agw-dow { display: block; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--text-3); }
.agw-num { display: block; font-size: 1.15rem; font-weight: 800; color: var(--text); line-height: 1.15; }
.agw-row.is-today .agw-dow, .agw-row.is-today .agw-num { color: var(--brand); }

/* Иконка дисциплины в плитке, окрашена по типу (--dot/--dotbg из t-*) */
.agw-ico {
  flex: none; width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center;
  background: var(--dotbg, var(--surface-3)); color: var(--dot, var(--text-3)); font-size: 0.92rem; margin-top: 1px;
}

.agw-body { flex: 1; min-width: 0; }
.agw-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.agw-label { font-weight: 700; font-size: 0.92rem; }
.agw-desc { margin: 4px 0 0; font-size: 0.84rem; line-height: 1.45; color: var(--text-2); }
.agw-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }

.agw-action { flex: none; display: flex; align-items: center; gap: 8px; padding-top: 2px; }

/* Рест-день — приглушённый */
.agw-row.is-rest .agw-label { color: var(--text-3); font-weight: 600; }
.agw-row.is-rest .agw-ico { color: var(--text-3); background: var(--surface-3); }

/* Палитра типов (задаёт --dot/--dotbg для иконки) */
.t-easy     { --dot: var(--green);  --dotbg: var(--green-dim); }
.t-tempo    { --dot: var(--yellow); --dotbg: var(--yellow-dim); }
.t-interval { --dot: var(--red);    --dotbg: var(--red-dim); }
.t-long     { --dot: var(--blue);   --dotbg: var(--blue-dim); }
.t-recovery { --dot: var(--text-3); --dotbg: var(--surface-3); }
.t-rest     { --dot: var(--text-3); --dotbg: var(--surface-3); }

/* Статус переопределяет окраску иконки */
.agw-row.s-done .agw-ico        { color: var(--green);  background: var(--green-dim); }
.agw-row.s-missed .agw-ico      { color: var(--red);    background: var(--red-dim); }
.agw-row.s-unconfirmed .agw-ico { color: var(--yellow); background: var(--yellow-dim); }

/* ── Мобилка ── */
@media (max-width: 560px) {
  .agw-row { display: grid; grid-template-columns: 34px 32px 1fr; column-gap: 10px; row-gap: 8px; align-items: start; }
  .agw-date { width: auto; padding-top: 0; }
  .agw-num { font-size: 1.05rem; }
  .agw-ico { margin-top: 0; }
  .agw-action { grid-column: 1 / -1; padding-top: 0; }
  .wk-head { gap: 6px; }
}
</style>

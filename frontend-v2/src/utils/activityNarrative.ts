// Форматирование нарратива тренировки — порт buildNarrative() из gpx-analyzer/index.html.
// Вся "умная" логика (детекция интервалов, тип бег/ходьба, пороги) уже посчитана на
// бэкенде (activity_analysis.py) — здесь только шаблонизация готовых фактов в предложения,
// без калиброванных порогов, чтобы вся логика калибровки жила в одном месте.
import type { ActivityAnalysis, ActivitySplit, IntervalSegment } from '@/api/types'

export function fmtPace(p: number | null | undefined): string {
  if (p == null || !isFinite(p) || p <= 0) return '—'
  let m = Math.floor(p)
  let s = Math.round((p - m) * 60)
  if (s === 60) { s = 0; m += 1 }
  return `${m}:${String(s).padStart(2, '0')}`
}

function plural(n: number): string {
  const m = n % 10, m100 = n % 100
  if (m100 >= 11 && m100 <= 14) return 'ов'
  if (m === 1) return ''
  if (m >= 2 && m <= 4) return 'а'
  return 'ов'
}

function avgOf(arr: (number | null)[]): number {
  const v = arr.filter((x): x is number => x != null && isFinite(x))
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0
}

export interface Narrative {
  badge: string
  sentences: string[]
}

export function buildNarrative(
  a: ActivityAnalysis,
  splits: ActivitySplit[] | null,
): Narrative {
  const sentences: string[] = []
  let badge = 'Равномерная тренировка'
  const actGen = a.activity_type.type === 'walk' ? 'прогулки' : 'пробежки'

  const iv = a.intervals
  if (iv) {
    badge = iv.kind === 'intervals' ? 'Интервальная тренировка' : 'Фартлек / ускорения'
    const repDist = Math.round(avgOf(iv.reps.map((r) => r.dist_m)))
    const repPace = avgOf(iv.reps.map((r) => r.pace_min_km))
    const recDist = iv.recoveries.length ? Math.round(avgOf(iv.recoveries.map((r) => r.dist_m))) : null
    const recPace = iv.recoveries.length ? avgOf(iv.recoveries.map((r) => r.pace_min_km)) : null

    let lead = iv.kind === 'intervals'
      ? `Похоже на интервальную тренировку: <strong>${iv.reps.length} повтор${plural(iv.reps.length)} по ~${repDist} м</strong> в темпе <strong>${fmtPace(repPace)}/км</strong>`
      : `Похоже на фартлек: <strong>${iv.reps.length} ускорени${iv.reps.length === 1 ? 'е' : 'й'}</strong> разной длины (в среднем ~${repDist} м) в темпе около <strong>${fmtPace(repPace)}/км</strong>`
    if (recDist) lead += `, отдых между ними — ~${recDist} м трусцой в темпе ${fmtPace(recPace)}/км`
    lead += '.'
    sentences.push(lead)

    const wc: string[] = []
    if (iv.warmup) wc.push(`разминка ~${(iv.warmup.dist_m / 1000).toFixed(2)} км`)
    if (iv.cooldown) wc.push(`заминка ~${(iv.cooldown.dist_m / 1000).toFixed(2)} км`)
    if (wc.length) sentences.push(`Плюс ${wc.join(' и ')}.`)

    if (iv.extra_reps.length) {
      const exN = iv.extra_reps.length
      const exDist = Math.round(avgOf(iv.extra_reps.map((r) => r.dist_m)))
      sentences.push(
        `${exN === 1 ? 'Ещё был один короткий всплеск' : `Ещё было ${exN} коротких всплеска`} (~${exDist} м) — в набор не считаем: заметно короче остальных повторов или не держит темп плато внутри себя (похоже на случайный скачок — светофор, GPS-шум и т.п.).`
      )
    }
  } else {
    const ns = a.negative_split
    if (ns) {
      if (ns.diff_pct < -1.5) {
        badge = 'Негативный сплит'
        sentences.push(`Вторая половина ${actGen} быстрее первой на <strong>${Math.abs(ns.diff_pct).toFixed(1)}%</strong> — хороший контроль темпа.`)
      } else if (ns.diff_pct > 1.5) {
        badge = 'Позитивный сплит'
        sentences.push(`Вторая половина медленнее первой на <strong>${ns.diff_pct.toFixed(1)}%</strong> — обычно так и есть на длинных или тяжёлых тренировках.`)
      } else {
        sentences.push(`Темп по дистанции ровный — разница между половинами ${actGen} меньше 1.5%.`)
      }
    }
    if (a.pace_consistency != null) {
      const c = a.pace_consistency
      const stabLabel = c < 0.03 ? 'очень стабильный' : c < 0.07 ? 'стабильный' : 'неровный'
      sentences.push(`Темп по километрам — <strong>${stabLabel}</strong> (разброс ${(c * 100).toFixed(1)}%).`)
    }
  }

  if (a.hr_decoupling != null && a.hr_decoupling > 5) {
    sentences.push(
      `Пульс «подъедает» темп к концу тренировки — эффективность (скорость на удар пульса) упала на <strong>${a.hr_decoupling.toFixed(1)}%</strong> во второй половине. Это нормально для длинных/жарких тренировок, но может говорить и о недовосстановлении.`
    )
  }

  const validSplits = (splits || []).filter((s) => s.pace != null)
  if (validSplits.length) {
    const best = validSplits.reduce((a, b) => ((a.pace ?? Infinity) <= (b.pace ?? Infinity) ? a : b))
    sentences.push(`Лучший километр — №${best.km}, ${fmtPace(best.pace)}/км.`)
  }

  if (a.pauses.count > 0) {
    sentences.push(`Остановок: ${a.pauses.count} (суммарно ${fmtDur(a.pauses.total_sec)}).`)
  }

  return { badge, sentences }
}

export function fmtDur(sec: number): string {
  sec = Math.round(sec)
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`
}

// Интерполяция значения по накопленной дистанции — тот же приём, что interpAt в прототипе,
// нужен чтобы наложить границы интервалов (в метрах) на разреженный track_points.
export function interpAt(targetDist: number, cumDist: number[], arr: number[]): number {
  let lo = 0, hi = cumDist.length - 1
  if (targetDist <= cumDist[0]) return arr[0]
  if (targetDist >= cumDist[hi]) return arr[hi]
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cumDist[mid] <= targetDist) lo = mid
    else hi = mid
  }
  const d0 = cumDist[lo], d1 = cumDist[hi]
  const f = d1 > d0 ? (targetDist - d0) / (d1 - d0) : 0
  return arr[lo] + (arr[hi] - arr[lo]) * f
}

export function allIntervalSegments(a: ActivityAnalysis): IntervalSegment[] {
  return a.intervals?.segments ?? []
}

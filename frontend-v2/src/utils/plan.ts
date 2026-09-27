// Хелперы отображения плана в формате отрезков (plan_structure.version === 2).
// Все числа считает бэкенд по зонам пользователя (resolved) — здесь только форматирование.
import type { PlanStructure, PlanStructureV2, ResolvedSegment, Workout } from '@/api/types'
import { fmtPace } from '@/utils/activityNarrative'

export function isV2(ps: Workout['plan_structure']): ps is PlanStructureV2 {
  return !!ps && (ps as PlanStructureV2).version === 2 && !!(ps as PlanStructureV2).resolved
}

export function isLegacy(ps: Workout['plan_structure']): ps is PlanStructure {
  return !!ps && Array.isArray((ps as PlanStructure).main)
}

/** «6:00–6:30» — диапазон темпа: быстрее–медленнее. */
export function fmtRange(r: [number, number] | null | undefined): string | null {
  if (!r) return null
  return `${fmtPace(r[0])}–${fmtPace(r[1])}`
}

export function fmtHr(r: [number, number] | null | undefined): string | null {
  if (!r) return null
  return `${r[0]}–${r[1]}`
}

/** 42 -> «42 мин», 65 -> «1 ч 05 мин». */
export function fmtDuration(min: number | null | undefined, hourUnit = 'ч', minUnit = 'мин'): string | null {
  if (min == null || !isFinite(min)) return null
  const total = Math.round(min)
  if (total < 60) return `${total} ${minUnit}`
  return `${Math.floor(total / 60)} ${hourUnit} ${String(total % 60).padStart(2, '0')} ${minUnit}`
}

export function fmtSeconds(s: number, minUnit = 'мин', secUnit = 'сек'): string {
  return s % 60 === 0 && s >= 60 ? `${s / 60} ${minUnit}` : `${s} ${secUnit}`
}

export const WALK_COLOR = 'color-mix(in srgb, var(--text-3) 40%, transparent)'

/** Цвет зоны для графика (палитра приложения). Трусца-восстановление — светло-зелёная (лёгкая зона). */
export function zoneColorByKey(zone: string | undefined): string {
  switch (zone) {
    case 'interval': return 'var(--red)'
    case 'tempo': return 'var(--yellow)'
    case 'long': return 'var(--blue)'
    case 'recovery': return 'color-mix(in srgb, var(--green) 45%, transparent)'
    default: return 'var(--green)'
  }
}

export function zoneColor(seg: ResolvedSegment): string {
  return seg.kind === 'walk' ? WALK_COLOR : zoneColorByKey(seg.zone)
}

/** Насколько блок выше базовой высоты, px: темп +1, интервалы +2 (высота = интенсивность). */
export function zoneLift(zone: string | undefined): number {
  return zone === 'interval' ? 2 : zone === 'tempo' ? 1 : 0
}

/** Вес отрезка для ширины на графике: длительность, иначе дистанция, иначе 1. */
export function segmentWeight(seg: ResolvedSegment): number {
  if (seg.duration_min && seg.duration_min > 0) return seg.duration_min
  if (seg.distance_km && seg.distance_km > 0) return seg.distance_km * 6
  return 1
}

/** Ключ i18n заголовка отрезка. */
export function segmentTitleKey(seg: ResolvedSegment): string {
  switch (seg.kind) {
    case 'warmup': return 'plan.seg.warmup'
    case 'cooldown': return 'plan.seg.cooldown'
    case 'steady': return 'plan.seg.steady'
    case 'intervals': return 'plan.seg.intervals'
    case 'run_walk': return 'plan.seg.runWalk'
    case 'walk': return 'plan.seg.walk'
    default: return `plan.segZone.${seg.zone ?? 'easy'}`
  }
}

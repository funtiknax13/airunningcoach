// Разбор пользовательского ввода времени и темпа.

/** «32:15» -> 32.25 мин, «1:05:30» -> 65.5 мин, «45» -> 45 мин. null — не разобрали. */
export function parseDuration(input: string): number | null {
  const s = (input || '').trim().replace(',', '.')
  if (!s) return null
  const parts = s.split(':').map(p => p.trim())
  if (parts.some(p => p === '' || !/^\d+(\.\d+)?$/.test(p))) return null
  const nums = parts.map(Number)
  if (nums.length === 1) return nums[0] > 0 ? nums[0] : null
  if (nums.length === 2) {
    const [m, sec] = nums
    return sec < 60 && m + sec > 0 ? m + sec / 60 : null
  }
  if (nums.length === 3) {
    const [h, m, sec] = nums
    return m < 60 && sec < 60 && h + m + sec > 0 ? h * 60 + m + sec / 60 : null
  }
  return null
}

/** «7:30» -> 7.5 мин/км; допускается только формат мм:сс. */
export function parsePace(input: string): number | null {
  const s = (input || '').trim()
  const m = /^(\d{1,2}):([0-5]\d)$/.exec(s)
  if (!m) return null
  const v = Number(m[1]) + Number(m[2]) / 60
  return v >= 3 && v <= 14 ? v : null
}

/** 7.5 -> «7:30» для подстановки в поля ввода. */
export function paceToInput(p: number | null | undefined): string {
  if (p == null || !isFinite(p)) return ''
  let m = Math.floor(p)
  let s = Math.round((p - m) * 60)
  if (s === 60) { s = 0; m += 1 }
  return `${m}:${String(s).padStart(2, '0')}`
}

/** 32.25 -> «32:15»; больше часа -> «1:05:30». */
export function durationToInput(min: number | null | undefined): string {
  if (min == null || !isFinite(min)) return ''
  const total = Math.round(min * 60)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

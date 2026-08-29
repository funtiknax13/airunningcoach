// Атрибуция регистрации по UTM-меткам из ссылки (блог/тулзы уже проставляют
// ?utm_source=blog&utm_medium=cta&utm_campaign=... в CTA, но раньше это нигде
// не сохранялось). Ловим на любой странице, где они есть в URL, храним до
// момента регистрации — модалка может открыться не сразу после захода.
const KEY = 'utm_params'

interface UtmParams {
  utm_source?: string
  utm_medium?: string
  utm_campaign?: string
}

export function captureUtmFromUrl(): void {
  const params = new URLSearchParams(window.location.search)
  const utm_source = params.get('utm_source') ?? undefined
  const utm_medium = params.get('utm_medium') ?? undefined
  const utm_campaign = params.get('utm_campaign') ?? undefined
  if (!utm_source && !utm_medium && !utm_campaign) return
  try {
    localStorage.setItem(KEY, JSON.stringify({ utm_source, utm_medium, utm_campaign }))
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — просто не атрибутируем
  }
}

export function getStoredUtm(): UtmParams {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

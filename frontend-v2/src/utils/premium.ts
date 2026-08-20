// Форматирование остатка Premium-времени. Триал теперь 48 часов (не 14 дней) —
// счёт целыми днями на таком окне скачет неинформативно («2д»→«1д»→«0д» ещё
// когда часов 20+ реально осталось), поэтому под сутки показываем часы.
export function formatTimeLeft(until: string | null | undefined, locale: 'ru' | 'en' = 'ru'): string | null {
  if (!until) return null
  const ms = new Date(until).getTime() - Date.now()
  if (ms <= 0) return null
  const hours = Math.ceil(ms / 3_600_000)
  if (locale === 'en') {
    return hours < 24 ? `${hours}h` : `${Math.ceil(hours / 24)}d`
  }
  return hours < 24 ? `${hours}ч` : `${Math.ceil(hours / 24)}д`
}

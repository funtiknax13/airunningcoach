// Stale-while-revalidate кеш стора в localStorage: показываем сохранённые данные
// мгновенно при загрузке страницы, пока store.load() тихо обновляет их в фоне.
// Ключ версии — __BUILD_ID__ (меняется на каждой сборке), поэтому новый деплой
// сам сбрасывает старый кеш без ручной инвалидации.
const PREFIX = 'cache:'

export function loadCache<T>(name: string): T | null {
  try {
    const raw = localStorage.getItem(PREFIX + name)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed.v !== __BUILD_ID__) return null
    return parsed.data as T
  } catch {
    return null
  }
}

export function saveCache<T>(name: string, data: T): void {
  try {
    localStorage.setItem(PREFIX + name, JSON.stringify({ v: __BUILD_ID__, data }))
  } catch {
    // localStorage переполнен/недоступен (приватный режим) — не критично, просто без кеша
  }
}

// Вызывается при logout — иначе на общем устройстве следующий пользователь
// на миг увидел бы кешированные пробежки/цели предыдущего аккаунта.
export function clearCache(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith(PREFIX)) localStorage.removeItem(key)
  }
}

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import { api, isAuthenticated, ApiError } from '@/api/client'
import { clearCache } from '@/utils/cache'
import type { UserResponse, UserUpdate, PasswordChange } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserResponse | null>(null)
  const loggedIn = ref(isAuthenticated())

  async function loadMe() {
    if (!isAuthenticated()) return
    try {
      user.value = await authApi.me()
      loggedIn.value = true
      syncTimezone()
    } catch (e) {
      // Разлогиниваем ТОЛЬКО при реальном 401 (токен невалиден).
      // Таймаут / 5xx / сетевой сбой — временные: сохраняем сессию, токен не трогаем.
      if (e instanceof ApiError && e.status === 401) logout()
    }
  }

  // Тихо подтягиваем часовой пояс браузера — ловит и пользователей, заведённых
  // до появления этого поля (у них timezone = null), и переезды/смену системной зоны.
  function syncTimezone() {
    if (!user.value) return
    // Запрос не await'ится и не отменяется — если пользователь успеет разлогиниться
    // (или залогиниться другим аккаунтом) до ответа, .then() ниже не должен
    // затирать user.value чужими/устаревшими данными. Проверяем id на момент
    // ответа, а не просто "залогинен ли кто-то вообще".
    const forUserId = user.value.id
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (detected && detected !== user.value.timezone) {
      authApi.updateProfile({ timezone: detected })
        .then(u => { if (user.value?.id === forUserId) user.value = u })
        .catch(() => {})
    }
  }

  async function login(email: string, password: string, altcha?: string) {
    await authApi.login({ email, password, altcha })
    loggedIn.value = true
    await loadMe()
  }

  function logout() {
    authApi.logout()
    clearCache()
    user.value = null
    loggedIn.value = false
  }

  async function updateProfile(data: UserUpdate) {
    user.value = await authApi.updateProfile(data)
  }

  async function changePassword(data: PasswordChange) {
    await authApi.changePassword(data)
  }

  const token = { value: api.getToken() }

  return { user, loggedIn, token, loadMe, login, logout, updateProfile, changePassword }
})

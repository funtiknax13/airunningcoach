import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import { api, isAuthenticated, ApiError } from '@/api/client'
import type { UserResponse, UserUpdate, PasswordChange } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserResponse | null>(null)
  const loggedIn = ref(isAuthenticated())

  async function loadMe() {
    if (!isAuthenticated()) return
    try {
      user.value = await authApi.me()
      loggedIn.value = true
    } catch (e) {
      // Разлогиниваем ТОЛЬКО при реальном 401 (токен невалиден).
      // Таймаут / 5xx / сетевой сбой — временные: сохраняем сессию, токен не трогаем.
      if (e instanceof ApiError && e.status === 401) logout()
    }
  }

  async function login(email: string, password: string) {
    await authApi.login({ email, password })
    loggedIn.value = true
    await loadMe()
  }

  function logout() {
    authApi.logout()
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

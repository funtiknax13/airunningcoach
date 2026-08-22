import { defineStore } from 'pinia'
import { ref } from 'vue'
import { trainingApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { loadCache, saveCache } from '@/utils/cache'
import type { Workout } from '@/api/types'

export const useTrainingStore = defineStore('training', () => {
  // Все тренировки пользователя (план + история). Календарь строит из них
  // месячную сетку и навигацию по прошлым месяцам на клиенте. План может быть
  // на неделю/месяц/3 месяца вперёд (см. training.py).
  const all         = ref<Workout[]>(loadCache<Workout[]>('training') ?? [])
  const loading     = ref(false)   // true во время запроса generate
  const loadingPlan = ref(false)   // true во время первоначальной загрузки
  const generating  = ref(false)   // true пока длинный план собирается в фоне

  let pollTimer: ReturnType<typeof setInterval> | null = null
  let pollCount = 0
  const POLL_MAX = 96   // ~8 минут: с запасом на 3-месячный план; страховка от «зависшей» задачи
  function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } pollCount = 0 }
  function ensurePoll() { if (!pollTimer) { pollCount = 0; pollTimer = setInterval(refreshStatus, 5000) } }

  async function load() {
    loadingPlan.value = true
    try {
      all.value = await trainingApi.list()
      saveCache('training', all.value)
    } finally { loadingPlan.value = false }
  }

  // Опрос статуса фоновой генерации. running → показываем «готовится» и поллим;
  // как только done/failed — подтягиваем свежий план и гасим индикатор. Пережидает
  // и уход со страницы, и перезагрузку (статус живёт на сервере).
  async function refreshStatus() {
    try {
      const s = await trainingApi.planStatus()
      if (s.status === 'running' && pollCount++ < POLL_MAX) { generating.value = true; ensurePoll() }
      else {
        stopPoll()
        if (generating.value) { generating.value = false; await load() }
      }
    } catch { /* тихо — фоновый поллинг */ }
  }

  // weeks: 1 (неделя, синхронно) | 4 (месяц) | 12 (3 месяца, в фоне). Месяц/3мес —
  // только Premium (бэкенд отдаст 403 — ловится в UI).
  async function generate(weeks = 1, includeToday = false) {
    loading.value = true
    try {
      const res = await trainingApi.generatePlan(weeks, includeToday)
      if (res.status === 'running') { generating.value = true; ensurePoll() }
      else { await load() }
    } finally { loading.value = false }
  }

  async function completeWorkout(id: number, notes?: string) {
    const result = await trainingApi.completeWorkout(id, notes)
    if (result.ai_analysis_pending) useChatStore().refreshUnread()
    await load()
  }

  async function uncompleteWorkout(id: number) {
    await trainingApi.uncompleteWorkout(id)
    await load()
  }

  return { all, loading, loadingPlan, generating, load, generate, refreshStatus, completeWorkout, uncompleteWorkout }
})

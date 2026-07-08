import { defineStore } from 'pinia'
import { ref } from 'vue'
import { trainingApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { loadCache, saveCache } from '@/utils/cache'
import type { Workout } from '@/api/types'

export const useTrainingStore = defineStore('training', () => {
  // Отсортировано сервером по planned_date desc — первые 7 записей всегда
  // самые дальние по дате, то есть актуальный сгенерированный план (см.
  // комментарий в training.py: AI никогда не планирует дальше чем на 7 дней
  // вперёд, поэтому это не требует привязки к календарной неделе).
  const all         = ref<Workout[]>(loadCache<Workout[]>('training') ?? [])
  const loading     = ref(false)   // true во время generate
  const loadingPlan = ref(false)   // true во время первоначальной загрузки

  async function load() {
    loadingPlan.value = true
    try {
      all.value = await trainingApi.list()
      saveCache('training', all.value)
    } finally { loadingPlan.value = false }
  }

  async function generate() {
    loading.value = true
    try { await trainingApi.generatePlan(); await load() }
    finally { loading.value = false }
  }

  async function completeWorkout(id: number, notes?: string) {
    const result = await trainingApi.completeWorkout(id, notes)
    if (result.ai_analysis_pending) useChatStore().setUnread()
    await load()
  }

  async function uncompleteWorkout(id: number) {
    await trainingApi.uncompleteWorkout(id)
    await load()
  }

  return { all, loading, loadingPlan, load, generate, completeWorkout, uncompleteWorkout }
})

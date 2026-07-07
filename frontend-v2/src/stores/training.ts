import { defineStore } from 'pinia'
import { ref } from 'vue'
import { trainingApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { ApiError } from '@/api/client'
import { loadCache, saveCache } from '@/utils/cache'
import type { TrainingPlan } from '@/api/types'

export const useTrainingStore = defineStore('training', () => {
  const plan        = ref<TrainingPlan | null>(loadCache<TrainingPlan | null>('training') ?? null)
  const loading     = ref(false)   // true во время generate
  const loadingPlan = ref(false)   // true во время первоначальной загрузки

  async function load() {
    loadingPlan.value = true
    try {
      plan.value = await trainingApi.activePlan()
      saveCache('training', plan.value)
    } catch (e) {
      // 404 = плана действительно нет — сбрасываем (и кеш). Таймаут/сеть/5xx —
      // временные, оставляем как есть (кешированный или предыдущий план).
      if (e instanceof ApiError && e.status === 404) {
        plan.value = null
        saveCache('training', null)
      }
    } finally { loadingPlan.value = false }
  }

  async function generate() {
    loading.value = true
    try { plan.value = await trainingApi.generatePlan() }
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

  return { plan, loading, loadingPlan, load, generate, completeWorkout, uncompleteWorkout }
})

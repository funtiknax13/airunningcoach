import { defineStore } from 'pinia'
import { ref } from 'vue'
import { trainingApi } from '@/api'
import type { TrainingPlan } from '@/api/types'

export const useTrainingStore = defineStore('training', () => {
  const plan        = ref<TrainingPlan | null>(null)
  const loading     = ref(false)   // true во время generate
  const loadingPlan = ref(false)   // true во время первоначальной загрузки

  async function load() {
    loadingPlan.value = true
    try { plan.value = await trainingApi.activePlan() }
    catch { plan.value = null }
    finally { loadingPlan.value = false }
  }

  async function generate() {
    loading.value = true
    try { plan.value = await trainingApi.generatePlan() }
    finally { loading.value = false }
  }

  async function completeWorkout(id: number, notes?: string) {
    await trainingApi.completeWorkout(id, notes)
    await load()
  }

  async function uncompleteWorkout(id: number) {
    await trainingApi.uncompleteWorkout(id)
    await load()
  }

  return { plan, loading, loadingPlan, load, generate, completeWorkout, uncompleteWorkout }
})

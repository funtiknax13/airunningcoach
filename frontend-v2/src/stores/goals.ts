import { defineStore } from 'pinia'
import { ref } from 'vue'
import { goalsApi } from '@/api'
import { loadCache, saveCache } from '@/utils/cache'
import type { Goal, GoalCreate, GoalUpdate } from '@/api/types'

export const useGoalsStore = defineStore('goals', () => {
  const goals   = ref<Goal[]>(loadCache<Goal[]>('goals') ?? [])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      goals.value = await goalsApi.list()
      saveCache('goals', goals.value)
    } finally { loading.value = false }
  }

  async function create(data: GoalCreate)            { await goalsApi.create(data);          await load() }
  async function update(id: number, data: GoalUpdate){ await goalsApi.update(id, data);      await load() }
  async function achieve(id: number)                 { await goalsApi.achieve(id);           await load() }
  async function abandon(id: number)                 { await goalsApi.abandon(id);           await load() }
  async function reactivate(id: number)              { await goalsApi.reactivate(id);        await load() }
  async function remove(id: number)                  { await goalsApi.remove(id);            await load() }

  return { goals, loading, load, create, update, achieve, abandon, reactivate, remove }
})

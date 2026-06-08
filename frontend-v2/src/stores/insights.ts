import { defineStore } from 'pinia'
import { ref } from 'vue'
import { insightsApi } from '@/api'
import type { DashboardInsights } from '@/api/types'

export const useInsightsStore = defineStore('insights', () => {
  const data    = ref<DashboardInsights | null>(null)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try { data.value = await insightsApi.dashboard() }
    catch { data.value = null }
    finally { loading.value = false }
  }

  return { data, loading, load }
})

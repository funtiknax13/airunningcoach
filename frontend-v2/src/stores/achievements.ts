import { defineStore } from 'pinia'
import { ref } from 'vue'
import { achievementsApi } from '@/api'

export const useAchievementsStore = defineStore('achievements', () => {
  const unseenCount = ref(0)

  async function refreshUnseen() {
    try { unseenCount.value = (await achievementsApi.unseenCount()).count }
    catch { /* тихо — фоновый polling */ }
  }

  async function markSeen() {
    unseenCount.value = 0
    try { await achievementsApi.markSeen() } catch { /* при следующем refresh досчитается заново */ }
  }

  return { unseenCount, refreshUnseen, markSeen }
})

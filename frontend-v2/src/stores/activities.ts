import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { activitiesApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { loadCache, saveCache } from '@/utils/cache'
import type { Activity, ActivityCreate, ActivityUpdate } from '@/api/types'

const PAGE_SIZE = 7

export const useActivitiesStore = defineStore('activities', () => {
  // Гидратируем из localStorage синхронно — на перезагрузке страницы список
  // не пустой, пока load() тихо не обновит его свежими данными с сервера.
  const all     = ref<Activity[]>(loadCache<Activity[]>('activities') ?? [])
  const page    = ref(0)
  const loading = ref(false)

  const total   = computed(() => all.value.length)
  const pages   = computed(() => Math.ceil(total.value / PAGE_SIZE))
  const current = computed(() =>
    all.value.slice(page.value * PAGE_SIZE, (page.value + 1) * PAGE_SIZE)
  )

  async function load() {
    loading.value = true
    try {
      all.value = await activitiesApi.list()
      saveCache('activities', all.value)
    } finally { loading.value = false }
  }

  async function create(data: ActivityCreate) {
    const result = await activitiesApi.create(data)
    if (result.ai_analysis_pending) useChatStore().setUnread()
    await load()
  }

  async function update(id: number, data: ActivityUpdate) {
    await activitiesApi.update(id, data)
    await load()
  }

  async function remove(id: number) {
    await activitiesApi.remove(id)
    const maxPage = Math.max(0, Math.ceil((total.value - 1) / PAGE_SIZE) - 1)
    page.value = Math.min(page.value, maxPage)
    await load()
  }

  function setPage(p: number) { page.value = p }

  return { all, page, total, pages, current, loading, load, create, update, remove, setPage }
})

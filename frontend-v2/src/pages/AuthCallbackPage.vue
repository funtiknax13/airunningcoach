<template>
  <div style="display:flex;align-items:center;justify-content:center;min-height:100vh">
    <div style="text-align:center;color:var(--text-2)">
      <div v-if="error" style="color:var(--danger)">
        <div style="font-size:2rem;margin-bottom:12px">⚠️</div>
        <div>{{ error }}</div>
        <button class="auth-btn" style="margin-top:16px;max-width:200px" @click="$router.push('/')">
          На главную
        </button>
      </div>
      <div v-else>
        <div style="font-size:2rem;margin-bottom:12px">⏳</div>
        <div>Входим в систему…</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { setToken } from '@/api/client'
import { useActivitiesStore } from '@/stores/activities'
import { useGoalsStore } from '@/stores/goals'
import { useTrainingStore } from '@/stores/training'
import { useChatStore } from '@/stores/chat'
import { useInsightsStore } from '@/stores/insights'

const router     = useRouter()
const auth       = useAuthStore()
const activities = useActivitiesStore()
const goals      = useGoalsStore()
const training   = useTrainingStore()
const chat       = useChatStore()
const insights   = useInsightsStore()

const error = ref('')

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  const googleError = params.get('google_error')

  if (googleError || !token) {
    error.value = 'Не удалось войти через Google. Попробуйте ещё раз.'
    return
  }

  // Сохраняем токен и загружаем профиль
  setToken(token)
  try {
    await auth.loadMe()
    await Promise.all([activities.load(), goals.load(), training.load(), chat.load()])
    router.push('/dashboard')
    // Инсайты (LLM) — в фоне, не блокируем редирект
    insights.load().catch(() => {})
  } catch {
    error.value = 'Не удалось загрузить профиль. Попробуйте ещё раз.'
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="show" class="trial-overlay" @click.self="dismiss">
        <div class="trial-modal">
          <div class="trial-modal-header">
            <div class="trial-modal-icon">😢</div>
            <h2 class="trial-modal-title">Пробный период закончился</h2>
            <p class="trial-modal-sub">Ты переходишь на план <strong>Basic</strong></p>
          </div>

          <div class="trial-lose-title">Что перестаёт быть доступным:</div>
          <ul class="trial-lose-list">
            <li v-for="item in loseItems" :key="item">
              <i class="fas fa-times"></i> {{ item }}
            </li>
          </ul>

          <div class="trial-keep-title">Что остаётся бесплатно:</div>
          <ul class="trial-keep-list">
            <li v-for="item in keepItems" :key="item">
              <i class="fas fa-check"></i> {{ item }}
            </li>
          </ul>

          <div class="trial-modal-actions">
            <RouterLink to="/subscription" class="btn btn-primary trial-btn-premium" @click="dismiss">
              <i class="fas fa-crown"></i> Подробнее о Premium
            </RouterLink>
            <button class="btn btn-ghost trial-btn-basic" @click="dismiss">
              Продолжить на Basic
            </button>
          </div>

          <p class="trial-modal-note">
            Оплата скоро будет доступна. Следи за обновлениями!
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const dismissed = ref(false)

const justExpired = computed(() => {
  const user = auth.user
  if (!user) return false
  // Премиум был (is_premium=True в прошлом) но сейчас истёк
  if (!user.premium_until) return false
  const until = new Date(user.premium_until)
  const now = new Date()
  // Истёк не более 3 дней назад — показываем баннер
  const diffDays = (now.getTime() - until.getTime()) / 86_400_000
  return diffDays >= 0 && diffDays < 3
})

const show = computed(() => justExpired.value && !dismissed.value)

const DISMISSED_KEY = 'trial_expired_dismissed'

onMounted(() => {
  const saved = localStorage.getItem(DISMISSED_KEY)
  if (saved) dismissed.value = true
})

function dismiss() {
  dismissed.value = true
  localStorage.setItem(DISMISSED_KEY, '1')
}

const loseItems = [
  'Безлимитный чат с AI-тренером (лимит: 10 сообщений/день)',
  'Генерация персональных планов тренировок',
  'Детальная аналитика пробежек (сплиты, пульс, каденс)',
]

const keepItems = [
  'Запись всех пробежек и история активностей',
  'Импорт GPX/FIT файлов',
  'Цели и базовая статистика',
  'AI-тренер: 10 сообщений в день',
]
</script>

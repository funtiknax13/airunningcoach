<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="show" class="trial-overlay" @click.self="dismiss">
        <div class="trial-modal">
          <div class="trial-modal-header">
            <div class="trial-modal-icon">🙂</div>
            <h2 class="trial-modal-title">Ускоренный режим закончился</h2>
            <p class="trial-modal-sub">Аккаунт как был, так и остаётся <strong>бесплатным</strong></p>
          </div>

          <div class="trial-lose-title">Что меняется:</div>
          <ul class="trial-lose-list">
            <li v-for="item in changedItems" :key="item">
              <i class="fas fa-arrow-down"></i> {{ item }}
            </li>
          </ul>

          <div class="trial-keep-title">Что остаётся как есть:</div>
          <ul class="trial-keep-list">
            <li v-for="item in keepItems" :key="item">
              <i class="fas fa-check"></i> {{ item }}
            </li>
          </ul>

          <div class="trial-modal-actions">
            <RouterLink to="/subscription" class="btn btn-primary trial-btn-premium" @click="dismiss">
              <i class="fas fa-crown"></i> Посмотреть Premium
            </RouterLink>
            <button class="btn btn-ghost trial-btn-basic" @click="dismiss">
              Продолжить бесплатно
            </button>
          </div>

          <p class="trial-modal-note">
            Платить не обязательно — аккаунт продолжит работать в любом случае.
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

// Честно: лимиты действительно снижаются, а план на месяц становится Premium-only
// (единственный реальный feature-gate в продукте) — но чат и генерация планов
// (недельных) остаются доступны, просто с обычными бесплатными лимитами, а не
// «пропадают», как формулировка звучала раньше.
const changedItems = [
  'AI-тренер: 50 сообщений/час → 10 в день',
  'Планы: 10/час → 1 в день, план на месяц — только в Premium',
]

const keepItems = [
  'Запись всех пробежек и история активностей',
  'Импорт GPX/FIT файлов и разбор тренировок',
  'AI-тренер и генерация недельного плана — бесплатно',
  'Цели и базовая статистика',
]
</script>

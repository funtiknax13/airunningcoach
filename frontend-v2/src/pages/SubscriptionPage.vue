<template>
  <AppLayout>
    <div class="subs-page">

      <!-- Текущий план -->
      <div class="card subs-card">
        <div class="subs-hero" :class="isPremium ? 'subs-hero--premium' : 'subs-hero--basic'">
          <i class="fas" :class="isPremium ? 'fa-crown' : 'fa-user'"></i>
          <div>
            <div class="subs-plan-name">{{ isPremium ? 'Premium' : 'Basic' }}</div>
            <div class="subs-plan-sub" v-if="isPremium && premiumUntil">
              Активен до {{ formatDate(premiumUntil) }}
              <span v-if="daysLeft !== null" class="subs-days-left">(осталось {{ daysLeft }} дн.)</span>
            </div>
            <div class="subs-plan-sub" v-else-if="!isPremium">
              Бесплатный тариф
            </div>
          </div>
        </div>

        <!-- Сравнение планов -->
        <div class="subs-compare">
          <div class="subs-col">
            <div class="subs-col-header">Basic</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Запись пробежек</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Цели и планы</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Импорт GPX/FIT</div>
            <div class="subs-feature text-muted"><i class="fas fa-comments"></i> 5 запросов к тренеру/день</div>
            <div class="subs-feature text-muted"><i class="fas fa-calendar-week"></i> 1 план/день</div>
          </div>
          <div class="subs-col subs-col--premium">
            <div class="subs-col-header"><i class="fas fa-crown"></i> Premium</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Запись пробежек</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Цели и планы</div>
            <div class="subs-feature"><i class="fas fa-check"></i> Импорт GPX/FIT</div>
            <div class="subs-feature"><i class="fas fa-comments"></i> 50 запросов к тренеру/час</div>
            <div class="subs-feature"><i class="fas fa-calendar-week"></i> 10 планов/час</div>
          </div>
        </div>

        <!-- Оплата — заглушка -->
        <div class="subs-payment">
          <div class="subs-payment-title">
            <i class="fas fa-clock"></i> Оплата скоро будет доступна
          </div>
          <p class="subs-payment-desc">
            Мы работаем над подключением платёжной системы.<br>
            Пока вы можете пользоваться пробным Premium — он выдаётся автоматически на 7 дней при регистрации.
          </p>
          <button class="btn btn-primary" disabled style="opacity:0.5;cursor:not-allowed">
            <i class="fas fa-lock"></i> Оформить Premium — скоро
          </button>
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const isPremium = computed(() => {
  if (!auth.user?.is_premium) return false
  if (!auth.user.premium_until) return true
  return new Date(auth.user.premium_until) > new Date()
})

const premiumUntil = computed(() => auth.user?.premium_until ?? null)

const daysLeft = computed(() => {
  if (!premiumUntil.value) return null
  const diff = new Date(premiumUntil.value).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / 86_400_000))
})

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })
}
</script>

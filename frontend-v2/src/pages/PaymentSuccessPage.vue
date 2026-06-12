<template>
  <AppLayout>
    <div class="payment-success-wrap">
      <div class="card payment-success-card">

        <!-- Загрузка -->
        <template v-if="loading">
          <div class="payment-success-icon" style="color:var(--text-3)">
            <i class="fas fa-spinner fa-spin"></i>
          </div>
          <h2 class="payment-success-title">{{ locale === 'ru' ? 'Проверяем платёж...' : 'Checking payment...' }}</h2>
        </template>

        <!-- Успех -->
        <template v-else-if="status === 'succeeded'">
          <div class="payment-success-icon">
            <i class="fas fa-circle-check"></i>
          </div>
          <h2 class="payment-success-title">{{ t('subs.successTitle') }}</h2>
          <p class="payment-success-desc">{{ t('subs.successDesc') }}</p>
          <router-link to="/dashboard" class="btn btn-primary">
            {{ t('subs.successBtn') }}
          </router-link>
        </template>

        <!-- Отмена -->
        <template v-else-if="status === 'cancelled'">
          <div class="payment-success-icon" style="color:var(--text-3)">
            <i class="fas fa-circle-xmark"></i>
          </div>
          <h2 class="payment-success-title">
            {{ locale === 'ru' ? 'Платёж отменён' : 'Payment cancelled' }}
          </h2>
          <p class="payment-success-desc">
            {{ locale === 'ru' ? 'Вы можете попробовать снова в любое время.' : 'You can try again at any time.' }}
          </p>
          <router-link to="/subscription" class="btn btn-secondary">
            {{ locale === 'ru' ? 'Вернуться к тарифам' : 'Back to plans' }}
          </router-link>
        </template>

        <!-- Ожидание / неизвестно -->
        <template v-else>
          <div class="payment-success-icon" style="color:var(--brand)">
            <i class="fas fa-clock"></i>
          </div>
          <h2 class="payment-success-title">
            {{ locale === 'ru' ? 'Платёж обрабатывается' : 'Payment is processing' }}
          </h2>
          <p class="payment-success-desc">
            {{ locale === 'ru'
              ? 'Обычно занимает до минуты. Обновите страницу или проверьте раздел подписки.'
              : 'Usually takes up to a minute. Refresh the page or check the subscription section.' }}
          </p>
          <router-link to="/subscription" class="btn btn-secondary">
            {{ locale === 'ru' ? 'Перейти к подписке' : 'Go to subscription' }}
          </router-link>
        </template>

      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const { t, locale } = useI18n()
const auth = useAuthStore()

const loading = ref(true)
const status  = ref<string>('pending')

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const ref_id = params.get('ref')

  if (!ref_id) {
    // Старый return_url без ref — просто обновляем профиль
    await auth.loadMe()
    status.value = 'succeeded'
    loading.value = false
    return
  }

  try {
    const data = await api.request<{ status: string }>(`/api/payments/verify?ref=${ref_id}`, 'GET')
    status.value = data.status
    if (data.status === 'succeeded') await auth.loadMe()
  } catch {
    status.value = 'pending'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.payment-success-wrap {
  display: flex; justify-content: center; align-items: center;
  min-height: 60vh; padding: 24px;
}
.payment-success-card {
  max-width: 420px; width: 100%; text-align: center; padding: 48px 32px;
}
.payment-success-icon {
  font-size: 3.5rem; color: var(--green); margin-bottom: 20px;
}
.payment-success-title {
  font-size: 1.4rem; font-weight: 700; margin-bottom: 12px;
}
.payment-success-desc {
  color: var(--text-2); margin-bottom: 28px; line-height: 1.6;
}
</style>

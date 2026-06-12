<template>
  <AppLayout>
    <div class="payment-success-wrap">
      <div class="card payment-success-card">
        <div class="payment-success-icon">
          <i class="fas fa-circle-check"></i>
        </div>
        <h2 class="payment-success-title">{{ t('subs.successTitle') }}</h2>
        <p class="payment-success-desc">{{ t('subs.successDesc') }}</p>
        <router-link to="/dashboard" class="btn btn-primary">
          {{ t('subs.successBtn') }}
        </router-link>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

// Обновляем профиль — Premium должен уже быть активирован вебхуком
onMounted(() => auth.loadMe())
</script>

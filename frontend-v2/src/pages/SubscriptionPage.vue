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
              {{ t('subs.activeUntil') }} {{ formatDate(premiumUntil) }}
              <span v-if="daysLeft !== null" class="subs-days-left">({{ t('subs.daysLeft', { n: daysLeft }) }})</span>
            </div>
            <div class="subs-plan-sub" v-else-if="!isPremium">
              {{ t('subs.free') }}
            </div>
          </div>
        </div>

        <!-- Сравнение планов -->
        <div class="subs-compare">
          <div class="subs-col">
            <div class="subs-col-header">Basic</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featRuns') }}</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featGoals') }}</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featImport') }}</div>
            <div class="subs-feature text-muted"><i class="fas fa-comments"></i> {{ t('subs.featBasicAi') }}</div>
            <div class="subs-feature text-muted"><i class="fas fa-calendar-week"></i> {{ t('subs.featBasicPlan') }}</div>
          </div>
          <div class="subs-col subs-col--premium">
            <div class="subs-col-header"><i class="fas fa-crown"></i> Premium</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featRuns') }}</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featGoals') }}</div>
            <div class="subs-feature"><i class="fas fa-check"></i> {{ t('subs.featImport') }}</div>
            <div class="subs-feature"><i class="fas fa-comments"></i> {{ t('subs.featProAi') }}</div>
            <div class="subs-feature"><i class="fas fa-calendar-week"></i> {{ t('subs.featProPlan') }}</div>
          </div>
        </div>

        <!-- Тарифы -->
        <div class="subs-plans">
          <div
            v-for="plan in plans" :key="plan.id"
            class="subs-plan-card"
            :class="{ 'subs-plan-card--popular': plan.popular, 'subs-plan-card--selected': selected === plan.id }"
            @click="selected = plan.id"
          >
            <div v-if="plan.badge" class="subs-plan-badge">{{ plan.badge }}</div>
            <div class="subs-plan-title">{{ plan.title }}</div>
            <div class="subs-plan-price">
              {{ plan.price }} ₽
              <span class="subs-plan-period">{{ plan.period }}</span>
            </div>
            <div v-if="plan.perMonth" class="subs-plan-per-month">{{ plan.perMonth }} ₽/{{ locale === 'ru' ? 'мес' : 'mo' }}</div>
            <div v-if="plan.discount" class="subs-plan-discount">{{ plan.discount }}</div>
          </div>
        </div>

        <!-- Кнопка оплаты -->
        <div class="subs-payment">
          <div v-if="payError" class="alert alert-error" style="margin-bottom:12px">
            <i class="fas fa-triangle-exclamation"></i> {{ payError }}
          </div>
          <button
            class="btn btn-primary subs-buy-btn"
            :disabled="paying"
            @click="startPayment"
          >
            <i class="fas" :class="paying ? 'fa-spinner fa-spin' : 'fa-credit-card'"></i>
            {{ paying ? t('subs.paying') : isPremium ? t('subs.extendBtn') : t('subs.buyBtn') }}
          </button>
          <p class="subs-payment-desc">{{ t('subs.paymentDesc') }}</p>

          <!-- ИНН самозанятого -->
          <div class="subs-inn">
            {{ locale === 'ru' ? 'Самозанятый. ИНН' : 'Self-employed. TIN' }}: <strong>211501982739</strong>
          </div>
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const { t, locale } = useI18n()
const auth = useAuthStore()

const selected = ref<'month' | 'quarter' | 'year'>('month')
const paying   = ref(false)
const payError = ref('')

async function startPayment() {
  paying.value = true
  payError.value = ''
  try {
    const res = await api.request<{ confirmation_url: string }>(
      '/api/payments/create', 'POST', { plan: selected.value }
    )
    window.location.href = res.confirmation_url
  } catch (e: any) {
    payError.value = e.message || t('subs.payError')
    paying.value = false
  }
}

const plans = computed(() => {
  const isRu = locale.value === 'ru'
  return [
    {
      id: 'month' as const,
      title: isRu ? '1 месяц' : '1 month',
      price: 490,
      period: isRu ? '/ мес' : '/ mo',
      perMonth: null,
      discount: null,
      badge: null,
      popular: false,
    },
    {
      id: 'quarter' as const,
      title: isRu ? '3 месяца' : '3 months',
      price: 1323,
      period: isRu ? '/ 3 мес' : '/ 3 mo',
      perMonth: 441,
      discount: isRu ? 'Скидка 10%' : '10% off',
      badge: null,
      popular: false,
    },
    {
      id: 'year' as const,
      title: isRu ? '1 год' : '1 year',
      price: 4116,
      period: isRu ? '/ год' : '/ year',
      perMonth: 343,
      discount: isRu ? 'Скидка 30%' : '30% off',
      badge: isRu ? '🔥 Выгоднее всего' : '🔥 Best value',
      popular: true,
    },
  ]
})

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
  return new Date(iso).toLocaleDateString(
    locale.value === 'ru' ? 'ru-RU' : 'en-US',
    { day: '2-digit', month: 'long', year: 'numeric' }
  )
}
</script>

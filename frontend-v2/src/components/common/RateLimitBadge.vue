<template>
  <div v-if="limits" class="rate-limit-badge">
    <div class="rlb-premium" v-if="limits.is_premium">
      <i class="fas fa-crown"></i>
      Premium
      <span v-if="limits.premium_until" class="rlb-until">
        до {{ formatDate(limits.premium_until) }}
      </span>
    </div>
    <div class="rlb-row">
      <i class="fas fa-comments"></i>
      <div class="rlb-bar-wrap">
        <div class="rlb-bar" :style="{ width: chatPct + '%' }" :class="{ danger: chatPct >= 90 }"></div>
      </div>
      <span class="rlb-count">{{ limits.chat.used }}/{{ limits.chat.limit }}
        <span class="rlb-window">{{ limits.chat.window === 'hour' ? '/ч' : '/д' }}</span>
      </span>
    </div>
    <div class="rlb-row">
      <i class="fas fa-calendar-week"></i>
      <div class="rlb-bar-wrap">
        <div class="rlb-bar" :style="{ width: planPct + '%' }" :class="{ danger: planPct >= 90 }"></div>
      </div>
      <span class="rlb-count">{{ limits.plan.used }}/{{ limits.plan.limit }}
        <span class="rlb-window">{{ limits.plan.window === 'hour' ? '/ч' : '/д' }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { authApi } from '@/api'
import type { RateLimitStatus } from '@/api/types'

const limits = ref<RateLimitStatus | null>(null)

onMounted(async () => {
  try { limits.value = await authApi.getLimits() } catch {}
})

const chatPct = computed(() =>
  limits.value ? Math.min(100, Math.round(limits.value.chat.used / limits.value.chat.limit * 100)) : 0
)
const planPct = computed(() =>
  limits.value ? Math.min(100, Math.round(limits.value.plan.used / limits.value.plan.limit * 100)) : 0
)

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' })
}
</script>

<template>
  <AppLayout>
    <div class="coach-layout">

      <!-- Chat panel -->
      <div class="card coach-chat-card">
        <div class="card-header" style="margin-bottom:12px">
          <div class="card-title"><i class="fas fa-robot"></i> {{ $t('chat.title') }}</div>
        </div>

        <div class="chat-messages" ref="boxRef">
          <div v-if="!chatStore.messages.length" class="chat-msg ai">
            <div class="chat-bubble">{{ $t('chat.greeting') }}</div>
          </div>
          <div v-for="(msg, i) in chatStore.messages" :key="msg.id"
               class="chat-msg" :class="msg.role">
            <div class="chat-bubble" v-if="msg.role !== 'ai'">{{ msg.content }}</div>
            <div v-else class="chat-ai-block">
              <div class="chat-bubble chat-bubble--md" v-html="renderMd(msg.content)" />
              <RouterLink v-if="msg.context_type === 'plan_generated'" to="/training"
                class="plan-ready-link">
                📅 {{ $t('chat.planReady') }}
              </RouterLink>
              <template v-if="msg.context_type === 'plan_proposal' && msg.plan_draft">
                <ChatPlanProposal :draft="msg.plan_draft" />
                <div v-if="i === chatStore.messages.length - 1" class="plan-confirm-row">
                  <button class="btn btn-primary btn-sm" :disabled="chatStore.confirming"
                          @click="confirmWeek(msg.id)">
                    {{ $t('chat.confirmWeek') }}
                  </button>
                  <button v-if="isPremium" class="btn btn-ghost btn-sm" :disabled="chatStore.confirming"
                          @click="confirmMonth()">
                    {{ $t('chat.confirmMonth') }}
                  </button>
                </div>
              </template>
            </div>
          </div>
          <div v-if="chatStore.typing" class="chat-msg ai">
            <div class="chat-bubble">
              <div class="typing-dot-wrap">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-row">
          <input class="chat-input" type="text" v-model="text"
                 :placeholder="$t('chat.placeholder')"
                 @keyup.enter="send" />
          <button class="btn btn-primary" @click="send" :disabled="chatStore.typing">
            <i class="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>

      <!-- Rate limit panel -->
      <RateLimitBadge ref="rateLimitBadge" />

      <!-- Insights panel -->
      <div class="card coach-insights-card">
        <div class="card-header" style="margin-bottom:12px">
          <div class="card-title"><i class="fas fa-brain"></i> {{ $t('ai.title') }}</div>
          <button class="btn btn-ghost btn-sm" @click="insightsStore.load()">
            <i class="fas fa-sync-alt"></i>
          </button>
        </div>
        <SkeletonLoader v-if="insightsStore.loading" type="insights" :count="4" />
        <div v-else-if="!insightsStore.data?.ai_insights?.length" class="empty-state">
          <i class="fas fa-robot"></i>
          <p>{{ $t('ai.empty') }}</p>
        </div>
        <div v-else v-for="(item, i) in insightsStore.data?.ai_insights" :key="i" class="insight-item">
          <i class="fas fa-lightbulb"></i>
          {{ item }}
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import RateLimitBadge from '@/components/common/RateLimitBadge.vue'
import ChatPlanProposal from '@/components/chat/ChatPlanProposal.vue'
import { useChatStore }     from '@/stores/chat'
import { useInsightsStore } from '@/stores/insights'
import { useTrainingStore } from '@/stores/training'
import { useAuthStore } from '@/stores/auth'
import { renderMd } from '@/utils/markdown'

const chatStore     = useChatStore()
const insightsStore = useInsightsStore()
const trainingStore = useTrainingStore()
const auth          = useAuthStore()
const router        = useRouter()
const { t }         = useI18n()
const text   = ref('')
const boxRef = ref<HTMLElement | null>(null)
const rateLimitBadge = ref<InstanceType<typeof RateLimitBadge> | null>(null)

const isPremium = computed(() => {
  if (!auth.user?.is_premium) return false
  if (!auth.user.premium_until) return true
  return new Date(auth.user.premium_until) > new Date()
})

async function confirmWeek(messageId: number) {
  try {
    await chatStore.confirmPlanDraft(messageId)
  } catch {
    chatStore.messages.push({
      id: Date.now(), role: 'ai', content: t('chat.confirmError'),
      context_type: 'general', created_at: new Date().toISOString(),
    })
  }
  scrollToBottom()
}

// "На месяц" — переиспользуем обычную генерацию плана на месяц (она уже умеет
// фон/опрос статуса на вкладке "Тренировки"); отдельного черновика с превью под
// эту кнопку пока не делаем — см. обсуждение в разговоре.
async function confirmMonth() {
  router.push('/training')
  await trainingStore.generate(4)
}

onMounted(async () => {
  chatStore.clearUnread()
  // Чат грузим сразу — он быстрый (просто история из БД)
  await chatStore.load()
  scrollToBottom()
  // Инсайты (LLM) — в фоне, не блокируем показ чата
  insightsStore.load().catch(() => {})
})

async function send() {
  const msg = text.value.trim()
  if (!msg) return
  text.value = ''
  await chatStore.send(msg)
  scrollToBottom()
  rateLimitBadge.value?.refresh()
}

function scrollToBottom() {
  nextTick(() => { if (boxRef.value) boxRef.value.scrollTop = boxRef.value.scrollHeight })
}

watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.typing, scrollToBottom)
</script>

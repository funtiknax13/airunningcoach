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
          <div v-for="msg in chatStore.messages" :key="msg.id"
               class="chat-msg" :class="msg.role">
            <div class="chat-bubble"
                 :class="{ 'chat-bubble--md': msg.role === 'ai' }"
                 v-if="msg.role === 'ai'"
                 v-html="renderMd(msg.content)" />
            <div class="chat-bubble" v-else>{{ msg.content }}</div>
            <RouterLink v-if="msg.context_type === 'plan_generated'" to="/training"
              class="plan-ready-link">
              📅 {{ $t('chat.planReady') }}
            </RouterLink>
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
import { ref, watch, nextTick, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { marked } from 'marked'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import RateLimitBadge from '@/components/common/RateLimitBadge.vue'
import { useChatStore }     from '@/stores/chat'
import { useInsightsStore } from '@/stores/insights'

marked.setOptions({ breaks: true, gfm: true })

const chatStore     = useChatStore()
const insightsStore = useInsightsStore()
const text   = ref('')
const boxRef = ref<HTMLElement | null>(null)
const rateLimitBadge = ref<InstanceType<typeof RateLimitBadge> | null>(null)

onMounted(async () => {
  chatStore.clearUnread()
  // Чат грузим сразу — он быстрый (просто история из БД)
  await chatStore.load()
  scrollToBottom()
  // Инсайты (LLM) — в фоне, не блокируем показ чата
  insightsStore.load().catch(() => {})
})

function renderMd(content: string) { return marked.parse(content) as string }

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

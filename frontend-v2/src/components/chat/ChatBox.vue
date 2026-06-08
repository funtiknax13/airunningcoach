<template>
  <div class="card">
    <div class="card-title"><i class="fas fa-comment-dots"></i> {{ $t('chat.title') }}</div>

    <div class="chat-messages-box" ref="boxRef">
      <div v-if="!store.messages.length" class="chat-message ai">
        <div class="message-bubble">{{ $t('chat.greeting') }}</div>
      </div>
      <div v-for="msg in store.messages" :key="msg.id"
           class="chat-message" :class="msg.role">
        <!-- AI сообщения рендерим через markdown, user — как plain text -->
        <div class="message-bubble"
             :class="{ 'message-bubble--md': msg.role === 'ai' }"
             v-if="msg.role === 'ai'"
             v-html="renderMd(msg.content)" />
        <div class="message-bubble" v-else>{{ msg.content }}</div>
      </div>
      <div v-if="store.typing" class="chat-message ai">
        <div class="message-bubble typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <div class="chat-input-row">
      <input type="text" v-model="text" :placeholder="$t('chat.placeholder')"
             @keyup.enter="send" />
      <button class="btn-primary" @click="send" :disabled="store.typing">
        <i class="fas fa-paper-plane"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { useChatStore } from '@/stores/chat'

const store  = useChatStore()
const text   = ref('')
const boxRef = ref<HTMLElement | null>(null)

// Настраиваем marked: без лишних <p> переносов, безопасно
marked.setOptions({ breaks: true, gfm: true })

function renderMd(content: string): string {
  return marked.parse(content) as string
}

async function send() {
  const msg = text.value.trim()
  if (!msg) return
  text.value = ''
  await store.send(msg)
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (boxRef.value) boxRef.value.scrollTop = boxRef.value.scrollHeight
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.typing, scrollToBottom)
</script>


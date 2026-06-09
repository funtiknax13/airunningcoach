<template>
  <div class="card">
    <div class="card-title"><i class="fas fa-comment-dots"></i> {{ $t('chat.title') }}</div>

    <div class="chat-messages" ref="boxRef">
      <div v-if="!store.messages.length" class="chat-msg ai">
        <div class="chat-bubble">{{ $t('chat.greeting') }}</div>
      </div>
      <div v-for="msg in store.messages" :key="msg.id"
           class="chat-msg" :class="msg.role">
        <div v-if="msg.role === 'ai'"
             class="chat-bubble chat-bubble--md"
             v-html="renderMd(msg.content)" />
        <div v-else class="chat-bubble">{{ msg.content }}</div>
      </div>
      <div v-if="store.typing" class="chat-msg ai">
        <div class="chat-bubble">
          <div class="typing-dot-wrap">
            <div class="typing-dot"></div><div class="typing-dot" style="animation-delay:.2s"></div><div class="typing-dot" style="animation-delay:.4s"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-row">
      <input class="chat-input" type="text" v-model="text" :placeholder="$t('chat.placeholder')"
             @keyup.enter="send" />
      <button class="btn btn-primary" @click="send" :disabled="store.typing">
        <i class="fas fa-paper-plane"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
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

onMounted(() => scrollToBottom())
watch(() => store.messages.length, scrollToBottom)
watch(() => store.typing, scrollToBottom)
</script>


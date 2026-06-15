import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api'
import { i18n } from '@/i18n'
import type { ChatMessage } from '@/api/types'

export const useChatStore = defineStore('chat', () => {
  const messages  = ref<ChatMessage[]>([])
  const typing    = ref(false)
  const hasUnread = ref(localStorage.getItem('ai_unread') === '1')

  function setUnread() {
    localStorage.setItem('ai_unread', '1')
    hasUnread.value = true
  }
  function clearUnread() {
    localStorage.removeItem('ai_unread')
    hasUnread.value = false
  }

  async function load() {
    messages.value = await chatApi.history()
  }

  async function send(text: string) {
    const lang = i18n.global.locale.value
    const userMsg: ChatMessage = {
      id: Date.now(), role: 'user', content: text,
      context_type: 'general', created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)
    typing.value = true
    try {
      const reply = await chatApi.send(text, lang)
      messages.value.push(reply)
    } catch (err: any) {
      const msg = err?.message?.includes('rate_limit') || err?.message?.includes('Лимит')
        ? err.message
        : i18n.global.t('chat.error')
      messages.value.push({
        id: Date.now() + 1, role: 'ai',
        content: msg,
        context_type: 'general', created_at: new Date().toISOString(),
      })
    } finally {
      typing.value = false
    }
  }

  return { messages, typing, hasUnread, setUnread, clearUnread, load, send }
})

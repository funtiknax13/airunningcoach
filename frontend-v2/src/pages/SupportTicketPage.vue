<template>
  <AppLayout>
    <template #header-actions>
      <RouterLink to="/support" class="btn btn-secondary btn-sm">
        <i class="fas fa-arrow-left"></i> {{ t('support.back') }}
      </RouterLink>
    </template>

    <div v-if="loading" class="card empty-state"><p>{{ t('common.loading') }}</p></div>
    <div v-else-if="!ticket" class="card empty-state"><p>{{ t('support.notFound') }}</p></div>

    <template v-else>
      <div class="card thread-header" :class="isOpen ? 'is-open' : 'is-closed'">
        <span class="badge" :class="isOpen ? 'badge-active' : 'badge-abandoned'">
          {{ isOpen ? t('support.open') : t('support.closed') }}
        </span>
        <span class="thread-sub">{{ isOpen ? t('support.openHint') : t('support.closedHint') }}</span>
      </div>

      <div class="card thread-messages">
        <div v-for="m in ticket.messages" :key="m.id" class="msg" :class="m.is_staff ? 'staff' : 'me'">
          <div class="msg-meta">
            <span class="msg-author">{{ m.is_staff ? t('support.staff') : t('support.you') }}</span>
            <time>{{ fmtTime(m.created_at) }}</time>
          </div>
          <p class="msg-body">{{ m.body }}</p>
        </div>
      </div>

      <div v-if="isOpen" class="card">
        <textarea v-model="reply" class="modal-input" rows="4" maxlength="5000"
                  :placeholder="t('support.replyPlaceholder')" />
        <div v-if="error" class="auth-error">{{ error }}</div>
        <div style="margin-top:10px">
          <button class="btn btn-primary" :disabled="sending || reply.trim().length === 0" @click="send">
            {{ sending ? t('support.sending') : t('support.send') }}
          </button>
        </div>
      </div>
      <div v-else class="card closed-note">
        {{ t('support.closedNote') }}
        <RouterLink to="/support">{{ t('support.createNew') }}</RouterLink>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { supportApi } from '@/api'
import { useSupportStore } from '@/stores/support'
import type { SupportTicketDetail } from '@/api/types'

const { t } = useI18n()
const route = useRoute()
const support = useSupportStore()
const id = Number(route.params.id)

const ticket = ref<SupportTicketDetail | null>(null)
const loading = ref(true)
const reply = ref('')
const sending = ref(false)
const error = ref('')

const isOpen = computed(() => ticket.value?.status === 'open')

function fmtTime(s: string) { return new Date(s).toLocaleString() }

onMounted(async () => {
  try {
    ticket.value = await supportApi.ticket(id)  // помечает ответы поддержки прочитанными
    support.refreshUnread()                     // бейдж в шапке пересчитается
  } finally {
    loading.value = false
  }
})

async function send() {
  if (reply.value.trim().length === 0) return
  error.value = ''
  sending.value = true
  try {
    ticket.value = await supportApi.reply(id, reply.value.trim())
    reply.value = ''
  } catch (e: any) {
    error.value = e?.message ?? t('support.errSend')
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.thread-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.thread-sub { color: var(--text-muted, #888); font-size: 14px; }
.thread-messages { margin-bottom: 12px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 85%; padding: 10px 14px; border-radius: 12px; }
.msg.me    { align-self: flex-end;   background: var(--accent-soft, rgba(248,92,30,0.12)); }
.msg.staff { align-self: flex-start; background: var(--surface-alt, rgba(255,255,255,0.05)); }
.msg-meta { display: flex; gap: 10px; align-items: baseline; margin-bottom: 4px; }
.msg-author { font-weight: 700; font-size: 13px; }
.msg-meta time { color: var(--text-muted, #888); font-size: 11px; }
.msg-body { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.closed-note { color: var(--text-muted, #888); }
</style>

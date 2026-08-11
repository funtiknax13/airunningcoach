<template>
  <AppLayout>
    <div class="card" style="margin-bottom:16px">
      <h3 style="margin:0 0 6px">{{ t('support.newTitle') }}</h3>
      <p style="margin:0 0 12px;color:var(--text-muted,#888);font-size:14px">{{ t('support.newHint') }}</p>
      <textarea v-model="body" class="modal-input" rows="5" maxlength="5000"
                :placeholder="t('support.message')" />
      <div v-if="error" class="auth-error">{{ error }}</div>
      <div style="margin-top:10px">
        <button class="btn btn-primary" :disabled="sending || body.trim().length === 0" @click="submit">
          {{ sending ? t('support.sending') : t('support.send') }}
        </button>
      </div>
    </div>

    <h3 style="margin:0 0 10px">{{ t('support.myTickets') }}</h3>
    <div class="card">
      <div v-if="loading" class="empty-state"><p>{{ t('common.loading') }}</p></div>
      <div v-else-if="!tickets.length" class="empty-state">
        <i class="fas fa-life-ring"></i>
        <p>{{ t('support.empty') }}</p>
      </div>
      <RouterLink v-else v-for="tk in tickets" :key="tk.id" :to="`/support/tickets/${tk.id}`" class="ticket-row">
        <span class="badge" :class="tk.status === 'open' ? 'badge-active' : 'badge-abandoned'">
          {{ tk.status === 'open' ? t('support.open') : t('support.closed') }}
        </span>
        <span class="ticket-preview">{{ tk.preview }}</span>
        <span v-if="tk.has_unread" class="ticket-new">{{ t('support.newReply') }}</span>
        <time class="ticket-date">{{ fmtDate(tk.created_at) }}</time>
      </RouterLink>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { supportApi } from '@/api'
import { useSupportStore } from '@/stores/support'
import type { SupportTicketSummary } from '@/api/types'

const { t } = useI18n()
const support = useSupportStore()

const tickets = ref<SupportTicketSummary[]>([])
const loading = ref(true)
const body = ref('')
const sending = ref(false)
const error = ref('')

function fmtDate(s: string) { return new Date(s).toLocaleDateString() }

async function load() {
  loading.value = true
  try { tickets.value = await supportApi.myTickets() }
  finally { loading.value = false }
}

async function submit() {
  error.value = ''
  if (body.value.trim().length === 0) return
  sending.value = true
  try {
    await supportApi.createTicket(body.value.trim())
    body.value = ''
    await load()
    support.refreshUnread()
  } catch (e: any) {
    error.value = e?.message ?? t('support.errSend')
  } finally {
    sending.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ticket-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 8px; border-bottom: 1px solid var(--border, #2a2a3a);
  text-decoration: none; color: inherit;
}
.ticket-row:last-child { border-bottom: none; }
.ticket-row:hover { background: var(--surface-hover, rgba(255,255,255,0.03)); }
.ticket-preview { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ticket-new {
  background: #ef4444; color: #fff; font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 999px; white-space: nowrap;
}
.ticket-date { color: var(--text-muted, #888); font-size: 12px; white-space: nowrap; }
</style>

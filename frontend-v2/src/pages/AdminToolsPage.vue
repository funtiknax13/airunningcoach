<template>
  <AppLayout>
    <template #header-actions>
      <button v-if="selected" class="btn btn-secondary btn-sm" @click="closeThread">
        <i class="fas fa-arrow-left"></i> {{ t('admin.support.backList') }}
      </button>
      <a v-else href="/sqladmin/" class="btn btn-secondary btn-sm">
        <i class="fas fa-database"></i> {{ t('admin.support.sqlAdmin') }}
      </a>
    </template>

    <!-- ── Список тикетов ── -->
    <template v-if="!selected">
      <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap">
        <button v-for="f in filters" :key="f.key" class="btn btn-sm"
          :class="statusFilter === f.key ? 'btn-primary' : 'btn-secondary'"
          @click="setFilter(f.key)">{{ f.label }}</button>
      </div>

      <div class="card">
        <div v-if="loading" class="empty-state"><p>{{ t('common.loading') }}</p></div>
        <div v-else-if="!rows.length" class="empty-state">
          <i class="fas fa-inbox"></i><p>{{ t('admin.support.empty') }}</p>
        </div>
        <button v-else v-for="r in rows" :key="r.id" class="ticket-row" @click="openTicket(r.id)">
          <span class="badge" :class="r.status === 'open' ? 'badge-active' : 'badge-abandoned'">
            {{ r.status === 'open' ? t('support.open') : t('support.closed') }}
          </span>
          <span v-if="r.unread" class="pill pill-new">{{ t('admin.support.new') }}</span>
          <span v-else-if="r.awaiting_reply" class="pill pill-await">{{ t('admin.support.awaiting') }}</span>
          <span class="ticket-who">{{ r.user_name || t('admin.support.deletedUser') }}</span>
          <span class="ticket-preview">{{ r.preview }}</span>
          <time class="ticket-date">{{ r.last_at ? fmtDate(r.last_at) : '' }}</time>
        </button>
      </div>

      <div v-if="totalPages > 1" class="pager">
        <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="go(page - 1)">‹</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-secondary btn-sm" :disabled="page >= totalPages" @click="go(page + 1)">›</button>
      </div>
    </template>

    <!-- ── Тред ── -->
    <template v-else>
      <div class="card thread-header">
        <span class="badge" :class="selected.status === 'open' ? 'badge-active' : 'badge-abandoned'">
          {{ selected.status === 'open' ? t('support.open') : t('support.closed') }}
        </span>
        <span class="thread-sub">{{ threadUser }}</span>
        <button class="btn btn-sm" :class="selected.status === 'open' ? 'btn-secondary' : 'btn-primary'"
          style="margin-left:auto" :disabled="toggling" @click="toggle">
          {{ selected.status === 'open' ? t('admin.support.close') : t('admin.support.reopen') }}
        </button>
      </div>

      <div class="card thread-messages">
        <div v-for="m in selected.messages" :key="m.id" class="msg" :class="m.is_staff ? 'staff' : 'user'">
          <div class="msg-meta">
            <span class="msg-author">{{ m.is_staff ? t('admin.support.staffYou') : threadUser }}</span>
            <time>{{ fmtTime(m.created_at) }}</time>
          </div>
          <p class="msg-body">{{ m.body }}</p>
        </div>
      </div>

      <div v-if="selected.status === 'open'" class="card">
        <textarea v-model="reply" class="modal-input" rows="4" maxlength="5000"
                  :placeholder="t('admin.support.replyPlaceholder')" />
        <div v-if="error" class="auth-error">{{ error }}</div>
        <div style="margin-top:10px">
          <button class="btn btn-primary" :disabled="sending || reply.trim().length === 0" @click="send">
            {{ sending ? t('support.sending') : t('admin.support.sendReply') }}
          </button>
        </div>
      </div>
      <div v-else class="card closed-note">{{ t('admin.support.closedNote') }}</div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { adminSupportApi } from '@/api'
import { useSupportStore } from '@/stores/support'
import type { AdminSupportRow, SupportTicketDetail } from '@/api/types'

const { t } = useI18n()
const support = useSupportStore()

type Filter = 'all' | 'open' | 'closed'
const filters = computed(() => [
  { key: 'all' as Filter,    label: t('admin.support.filterAll') },
  { key: 'open' as Filter,   label: t('admin.support.filterOpen') },
  { key: 'closed' as Filter, label: t('admin.support.filterClosed') },
])

const rows = ref<AdminSupportRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const statusFilter = ref<Filter>('all')
const loading = ref(true)

const selected = ref<SupportTicketDetail | null>(null)
const selectedUser = ref<string>('')
const reply = ref('')
const sending = ref(false)
const toggling = ref(false)
const error = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const threadUser = computed(() => selectedUser.value || t('admin.support.deletedUser'))

function fmtDate(s: string) { return new Date(s).toLocaleDateString() }
function fmtTime(s: string) { return new Date(s).toLocaleString() }

async function load() {
  loading.value = true
  try {
    const res = await adminSupportApi.list(statusFilter.value, page.value)
    rows.value = res.tickets
    total.value = res.total
    pageSize.value = res.page_size
  } finally {
    loading.value = false
  }
  support.refreshStaffUnread()
}

function setFilter(f: Filter) { statusFilter.value = f; page.value = 1; load() }
function go(p: number) { page.value = p; load() }

async function openTicket(id: number) {
  const row = rows.value.find(r => r.id === id)
  selectedUser.value = row?.user_name || row?.user_email || ''
  selected.value = await adminSupportApi.ticket(id)  // помечает сообщения пользователя прочитанными
  support.refreshStaffUnread()
}

function closeThread() { selected.value = null; reply.value = ''; error.value = ''; load() }

async function send() {
  if (!selected.value || reply.value.trim().length === 0) return
  error.value = ''
  sending.value = true
  try {
    selected.value = await adminSupportApi.reply(selected.value.id, reply.value.trim())
    reply.value = ''
  } catch (e: any) {
    error.value = e?.message ?? t('support.errSend')
  } finally {
    sending.value = false
  }
}

async function toggle() {
  if (!selected.value) return
  toggling.value = true
  try {
    selected.value = await adminSupportApi.toggleStatus(selected.value.id)
  } finally {
    toggling.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ticket-row {
  display: flex; align-items: center; gap: 12px; width: 100%;
  padding: 12px 8px; border: none; background: none; cursor: pointer;
  text-align: left; color: inherit;
  border-bottom: 1px solid var(--border, #2a2a3a);
}
.ticket-row:last-child { border-bottom: none; }
.ticket-row:hover { background: var(--surface-hover, rgba(255,255,255,0.03)); }
.ticket-who { font-weight: 600; white-space: nowrap; }
.ticket-preview { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted, #999); }
.ticket-date { color: var(--text-muted, #888); font-size: 12px; white-space: nowrap; }
.pill { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.pill-new   { background: #ef4444; color: #fff; }
.pill-await { background: #f59e0b; color: #1a1a1a; }
.pager { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; }
.thread-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.thread-sub { color: var(--text-muted, #888); font-size: 14px; }
.thread-messages { margin-bottom: 12px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 85%; padding: 10px 14px; border-radius: 12px; }
.msg.staff { align-self: flex-end;   background: var(--accent-soft, rgba(248,92,30,0.12)); }
.msg.user  { align-self: flex-start; background: var(--surface-alt, rgba(255,255,255,0.05)); }
.msg-meta { display: flex; gap: 10px; align-items: baseline; margin-bottom: 4px; }
.msg-author { font-weight: 700; font-size: 13px; }
.msg-meta time { color: var(--text-muted, #888); font-size: 11px; }
.msg-body { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.closed-note { color: var(--text-muted, #888); }
</style>

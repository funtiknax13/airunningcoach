import { defineStore } from 'pinia'
import { ref } from 'vue'
import { supportApi, adminSupportApi } from '@/api'

export const useSupportStore = defineStore('support', () => {
  // Непрочитанные ответы поддержки для текущего пользователя (бейдж «Поддержка»).
  const unreadCount = ref(0)
  // Треды с непрочитанным от пользователей — бейдж «Admin Tools» (только для админа).
  const staffUnread = ref(0)

  // Тихий фоновый polling — ошибки не шумят (сеть/логаут).
  async function refreshUnread() {
    try { unreadCount.value = (await supportApi.unreadCount()).count }
    catch { /* ignore */ }
  }

  async function refreshStaffUnread() {
    try { staffUnread.value = (await adminSupportApi.badgeCounts()).tickets }
    catch { /* не админ (403) или сеть — тихо */ }
  }

  return { unreadCount, staffUnread, refreshUnread, refreshStaffUnread }
})

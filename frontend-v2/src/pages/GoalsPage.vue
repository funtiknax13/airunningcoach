<template>
  <AppLayout>
    <template #header-actions>
      <button class="btn btn-primary btn-sm" @click="modal?.open()">
        <i class="fas fa-plus"></i> {{ $t('goals.add') }}
      </button>
    </template>

    <!-- Filter tabs -->
    <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap">
      <button v-for="f in filters" :key="f.key"
        class="btn btn-sm"
        :class="activeFilter === f.key ? 'btn-primary' : 'btn-secondary'"
        @click="activeFilter = f.key">
        {{ f.label }} <span style="margin-left:4px;opacity:0.7">({{ f.count }})</span>
      </button>
    </div>

    <div class="card">
      <SkeletonLoader v-if="store.loading" type="goal-list" :count="4" />
      <div v-else-if="!filtered.length" class="empty-state">
        <i class="fas fa-bullseye"></i>
        <p>{{ $t('goals.empty') }}</p>
      </div>

      <div v-else v-for="g in filtered" :key="g.id" class="goal-item">
        <div class="goal-item-header">
          <span class="goal-item-title">{{ g.description || goalTypeLabel(g.goal_type) }}</span>
          <span class="badge"
            :class="g.is_achieved ? 'badge-achieved' : g.is_abandoned ? 'badge-abandoned' : 'badge-active'">
            {{ g.is_achieved ? $t('goals.status.achieved') : g.is_abandoned ? $t('goals.status.abandoned') : $t('goals.status.active') }}
          </span>
        </div>
        <div class="goal-item-meta">
          <span v-if="g.target_distance_km">🏃 {{ g.target_distance_km }} km</span>
          <span v-if="g.target_time_min">⏱ {{ formatGoalTime(g.target_time_min) }}</span>
          <span v-if="g.target_date">📅 {{ formatDate(g.target_date) }}</span>
        </div>
        <div v-if="g.description && g.goal_type !== 'custom'" class="goal-item-desc">{{ g.description }}</div>
        <div class="goal-item-actions">
          <button class="goal-action-btn goal-action-btn--edit"       @click="modal?.open(g.id)">{{ $t('goals.action.edit') }}</button>
          <button v-if="!g.is_achieved && !g.is_abandoned" class="goal-action-btn goal-action-btn--achieve"  @click="doAction(g.id, 'achieve')">{{ $t('goals.action.achieve') }}</button>
          <button v-if="!g.is_achieved && !g.is_abandoned" class="goal-action-btn goal-action-btn--abandon"  @click="doAction(g.id, 'abandon')">{{ $t('goals.action.abandon') }}</button>
          <button v-if="g.is_achieved || g.is_abandoned"  class="goal-action-btn goal-action-btn--reactivate" @click="store.reactivate(g.id)">{{ $t('goals.action.reactivate') }}</button>
          <button class="goal-action-btn goal-action-btn--delete"     @click="doAction(g.id, 'delete')">{{ $t('goals.action.delete') }}</button>
        </div>
      </div>
    </div>

    <GoalModal ref="modal" v-model="showModal" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import GoalModal from '@/components/goals/GoalModal.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import { useGoalsStore } from '@/stores/goals'
import { useDialog } from '@/composables/useDialog'
import type { GoalType } from '@/api/types'

const { t, locale } = useI18n()
const store     = useGoalsStore()
const modal     = ref<InstanceType<typeof GoalModal> | null>(null)
const showModal = ref(false)
const activeFilter = ref<'all'|'active'|'achieved'|'abandoned'>('all')
const { confirm } = useDialog()

onMounted(() => store.load())

const filters = computed(() => [
  { key: 'all'      as const, label: t('goals.filter.all'),      count: store.goals.length },
  { key: 'active'   as const, label: t('goals.filter.active'),   count: store.goals.filter(g => !g.is_achieved && !g.is_abandoned).length },
  { key: 'achieved' as const, label: t('goals.filter.achieved'), count: store.goals.filter(g => g.is_achieved).length },
  { key: 'abandoned'as const, label: t('goals.filter.abandoned'),count: store.goals.filter(g => g.is_abandoned).length },
])

const filtered = computed(() => {
  if (activeFilter.value === 'all')      return store.goals
  if (activeFilter.value === 'active')   return store.goals.filter(g => !g.is_achieved && !g.is_abandoned)
  if (activeFilter.value === 'achieved') return store.goals.filter(g => g.is_achieved)
  return store.goals.filter(g => g.is_abandoned)
})

function goalTypeLabel(type: GoalType) {
  const map: Record<string, string> = {
    half_marathon: t('goals.type.half_marathon'), full_marathon: t('goals.type.full_marathon'),
    '10k': t('goals.type.10k'), '5k': t('goals.type.5k'), custom: t('goals.type.custom'),
  }
  return map[type] ?? type
}
function formatGoalTime(min: number) {
  const h = Math.floor(min/60); const m = Math.round(min%60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(locale.value === 'ru' ? 'ru-RU' : 'en-US', { day:'numeric', month:'short', year:'numeric' })
}
async function doAction(id: number, action: 'achieve'|'abandon'|'delete') {
  const msgs: Record<typeof action, string> = {
    achieve: 'goals.confirmAchieve', abandon: 'goals.confirmAbandon', delete: 'goals.confirmDelete',
  }
  const ok = await confirm(t(msgs[action]), {
    danger: action === 'delete',
    confirmLabel: action === 'delete' ? t('btn.delete') : t('btn.confirm'),
    cancelLabel: t('btn.cancel'),
  })
  if (!ok) return
  if      (action === 'achieve') await store.achieve(id)
  else if (action === 'abandon') await store.abandon(id)
  else                           await store.remove(id)
}
</script>

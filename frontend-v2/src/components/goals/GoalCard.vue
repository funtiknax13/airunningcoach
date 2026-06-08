<template>
  <div class="goal-card" :class="{ 'goal-card--achieved': goal.is_achieved, 'goal-card--abandoned': goal.is_abandoned }">
    <div class="goal-card-header">
      <h4>{{ goalName(goal.goal_type) }}</h4>
      <span class="goal-badge" :class="badgeClass">{{ badgeText }}</span>
    </div>
    <div class="goal-card-body">
      <span v-if="goal.target_distance_km">📏 {{ goal.target_distance_km }} km</span>
      <span v-if="goal.target_time_min">⏱ {{ formatTime(goal.target_time_min) }}</span>
      <span v-if="goal.target_date">📅 {{ shortDate(goal.target_date) }}</span>
    </div>
    <p v-if="goal.description" class="goal-desc">{{ goal.description }}</p>
    <div class="goal-actions">
      <button class="goal-action-btn goal-action-btn--edit"
              @click="$emit('edit', goal.id)" :title="$t('goals.action.edit')">
        <i class="fas fa-pen"></i>
      </button>
      <template v-if="goal.is_active">
        <button class="goal-action-btn goal-action-btn--achieve"
                @click="$emit('achieve', goal.id)" :title="$t('goals.action.achieve')">
          <i class="fas fa-trophy"></i>
        </button>
        <button class="goal-action-btn goal-action-btn--abandon"
                @click="$emit('abandon', goal.id)" :title="$t('goals.action.abandon')">
          <i class="fas fa-times"></i>
        </button>
      </template>
      <template v-else>
        <button class="goal-action-btn goal-action-btn--reactivate"
                @click="$emit('reactivate', goal.id)" :title="$t('goals.action.reactivate')">
          <i class="fas fa-rotate-left"></i> {{ $t('goals.action.reactivate') }}
        </button>
        <button class="goal-action-btn goal-action-btn--delete"
                @click="$emit('delete', goal.id)" :title="$t('goals.action.delete')">
          <i class="fas fa-trash"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Goal } from '@/api/types'

const { t } = useI18n()
const props = defineProps<{ goal: Goal }>()
defineEmits<{
  (e: 'edit'|'achieve'|'abandon'|'reactivate'|'delete', id: number): void
}>()

const badgeClass = computed(() =>
  props.goal.is_achieved ? 'goal-badge--achieved'
  : props.goal.is_abandoned ? 'goal-badge--abandoned'
  : 'goal-badge--active'
)
const badgeText = computed(() =>
  props.goal.is_achieved ? t('goals.status.achieved')
  : props.goal.is_abandoned ? t('goals.status.abandoned')
  : t('goals.status.active')
)

const TYPE_MAP: Record<string, string> = {
  half_marathon: 'goals.name.halfMarathon', full_marathon: 'goals.name.fullMarathon',
  '10k': 'goals.name.10k', '5k': 'goals.name.5k', custom: 'goals.name.custom',
}
function goalName(type: string) { return t(TYPE_MAP[type] ?? type) }
function formatTime(min: number) {
  const h = Math.floor(min / 60); const m = Math.round(min % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}
</script>

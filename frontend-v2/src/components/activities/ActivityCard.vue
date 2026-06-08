<template>
  <div class="activity-item">
    <div class="activity-metrics">
      <span class="activity-metric activity-metric--dist">
        {{ activity.distance_km }} <small>{{ $t('misc.km', 'km') }}</small>
      </span>
      <span class="activity-metric activity-metric--pace">
        {{ formatPace(activity.pace_min_per_km) }} <small>/km</small>
      </span>
      <span class="activity-metric activity-metric--time">
        {{ formatDuration(activity.duration_min) }}
      </span>
      <span v-if="activity.avg_heart_rate" class="activity-metric activity-metric--hr">
        ♥ {{ activity.avg_heart_rate }}
      </span>
    </div>
    <div class="activity-meta">
      <span class="activity-date">{{ shortDate(activity.date) }}</span>
      <span v-if="activity.notes" class="activity-note">{{ activity.notes }}</span>
    </div>
    <div class="activity-actions">
      <button class="edit-btn"   @click="$emit('edit', activity.id)"   :title="$t('goals.action.edit')">
        <i class="fas fa-pen"></i>
      </button>
      <button class="delete-btn" @click="$emit('delete', activity.id)" :title="$t('activities.confirmDelete')">
        <i class="fas fa-trash"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Activity } from '@/api/types'

defineProps<{ activity: Activity }>()
defineEmits<{ (e: 'edit', id: number): void; (e: 'delete', id: number): void }>()

function formatPace(pace: number): string {
  const m = Math.floor(pace); const s = Math.round((pace - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function formatDuration(min: number): string {
  const h = Math.floor(min / 60); const m = Math.round(min % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })
}
</script>

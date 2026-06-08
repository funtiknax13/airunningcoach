<template>
  <div class="card">
    <div class="card-title"><i class="fas fa-chart-line"></i> {{ $t('stats.title') }}</div>
    <div class="info-grid">
      <div class="stat-badge">
        <i class="fas fa-road"></i>
        {{ $t('stats.km') }}
        <strong>{{ stats?.total_distance_km.toFixed(1) ?? '—' }}</strong>
      </div>
      <div class="stat-badge">
        <i class="fas fa-clock"></i>
        {{ $t('stats.time') }}
        <strong>{{ formatTime(stats?.total_time_min) }}</strong>
      </div>
      <div class="stat-badge">
        <i class="fas fa-tachometer-alt"></i>
        {{ $t('stats.pace') }}
        <strong>{{ formatPace(stats?.average_pace_min_km) }}</strong>
      </div>
      <div class="stat-badge">
        <i class="fas fa-calendar-check"></i>
        {{ $t('stats.count') }}
        <strong>{{ stats?.activities_count ?? '—' }}</strong>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DashboardStats } from '@/api/types'
defineProps<{ stats: DashboardStats | null | undefined }>()

function formatTime(min?: number) {
  if (!min) return '—'
  return `${Math.floor(min/60)}h ${Math.round(min%60)}m`
}
function formatPace(pace?: number) {
  if (!pace) return '—'
  const m = Math.floor(pace); const s = Math.round((pace-m)*60)
  return `${m}:${String(s).padStart(2,'0')} /km`
}
</script>

<template>
  <AppLayout>
    <div v-if="loading" class="card" style="padding:16px">
      <SkeletonLoader type="stat-grid" :count="8" />
    </div>

    <template v-else>
      <div v-if="genderRequired" class="card achievement-notice">
        <i class="fas fa-circle-info"></i>
        <span>{{ $t('achievements.genderRequired') }}</span>
        <button class="btn btn-primary btn-sm" @click="profileModal?.open()">
          {{ $t('achievements.genderRequiredCta') }}
        </button>
      </div>

      <p class="achievements-subtitle">{{ $t('achievements.subtitle') }}</p>

      <div class="stat-grid">
        <div v-for="r in records" :key="r.distance_key" class="stat-card achievement-card">
          <div class="stat-card-label"><i class="fas fa-flag-checkered"></i> {{ r.distance_label }}</div>

          <template v-if="r.matched">
            <div class="stat-card-value">{{ fmtTime(r.time_sec!) }}</div>
            <div class="achievement-pace">{{ fmtTime(r.pace_min_km! * 60) }} /км</div>

            <div v-if="r.achieved_rank_label" class="achievement-rank-badge">
              <i class="fas fa-medal"></i> {{ r.achieved_rank_label }}
            </div>
            <div v-else-if="!genderRequired" class="achievement-no-rank">{{ $t('achievements.noRank') }}</div>

            <div v-if="r.next_rank_label && r.gap_sec != null" class="achievement-gap">
              {{ $t('achievements.gapToNext') }} «{{ r.next_rank_label }}»: {{ fmtTime(r.gap_sec) }}
            </div>
          </template>
          <template v-else>
            <div class="achievement-empty">{{ $t('achievements.noRecord') }}</div>
            <div class="achievement-empty-hint">{{ $t('achievements.noRecordHint') }}</div>
          </template>
        </div>
      </div>
    </template>

    <ProfileModal ref="profileModal" v-model="showProfile" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import ProfileModal from '@/components/profile/ProfileModal.vue'
import { achievementsApi } from '@/api'
import type { AchievementRecord } from '@/api/types'

const loading = ref(true)
const genderRequired = ref(false)
const records = ref<AchievementRecord[]>([])
const profileModal = ref<InstanceType<typeof ProfileModal> | null>(null)
const showProfile = ref(false)

function fmtTime(totalSec: number): string {
  const s = Math.max(0, Math.round(totalSec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const secStr = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${secStr}` : `${m}:${secStr}`
}

onMounted(async () => {
  try {
    const res = await achievementsApi.list()
    genderRequired.value = res.gender_required
    records.value = res.records
  } finally {
    loading.value = false
  }
})
</script>

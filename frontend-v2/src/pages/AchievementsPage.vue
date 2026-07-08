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

      <h2 class="achievements-section-title">{{ $t('achievements.recordsTitle') }}</h2>
      <p class="achievements-subtitle">{{ $t('achievements.subtitle') }}</p>

      <div class="stat-grid">
        <div v-for="r in personalRecords" :key="r.distance_key" class="stat-card achievement-card">
          <div class="stat-card-label">
            <i :class="r.distance_key === 'longest' ? 'fas fa-route' : 'fas fa-flag-checkered'"></i> {{ r.distance_label }}
            <button v-if="r.matched" class="btn-share" :title="$t('achievements.shareBtn')" @click="onShareRecord(r)">
              <i class="fas fa-share-nodes"></i>
            </button>
          </div>

          <template v-if="r.matched">
            <template v-if="r.distance_key === 'longest'">
              <div class="stat-card-value">{{ r.distance_km?.toFixed(2) }} км</div>
              <div class="achievement-pace">{{ fmtTime(r.time_sec!) }}</div>
            </template>
            <template v-else>
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
          </template>
          <template v-else>
            <div class="achievement-empty">{{ $t('achievements.noRecord') }}</div>
            <div class="achievement-empty-hint">{{ $t('achievements.noRecordHint') }}</div>
          </template>
        </div>
      </div>

      <h2 class="achievements-section-title">{{ $t('achievements.badgesTitle') }}</h2>
      <p class="achievements-subtitle">{{ $t('achievements.badgesSubtitle') }}</p>

      <div class="badge-grid">
        <div v-for="b in badges" :key="b.key" class="badge-card" :class="{ unlocked: b.unlocked }">
          <button v-if="b.unlocked" class="btn-share btn-share--badge" :title="$t('achievements.shareBtn')" @click="onShareBadge(b)">
            <i class="fas fa-share-nodes"></i>
          </button>
          <div class="badge-icon"><img :src="b.icon_img" :alt="b.label" loading="lazy"></div>
          <div class="badge-label">{{ b.label }}</div>
          <div class="badge-desc">{{ b.description }}</div>
          <div v-if="b.unlocked && b.earned_at" class="badge-earned">{{ fmtDate(b.earned_at) }}</div>
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
import { useShareCard } from '@/composables/useShareCard'
import type { AchievementRecord, BadgeAchievement } from '@/api/types'

const { share } = useShareCard()

const loading = ref(true)
const genderRequired = ref(false)
const personalRecords = ref<AchievementRecord[]>([])
const badges = ref<BadgeAchievement[]>([])
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

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function onShareBadge(b: BadgeAchievement) {
  share({ emoji: '🏆', title: b.label, subtitle: b.description, utmCampaign: b.key, imageUrl: b.icon_img })
}

function onShareRecord(r: AchievementRecord) {
  const isLongest = r.distance_key === 'longest'
  const title = isLongest ? `${r.distance_km?.toFixed(2)} км` : fmtTime(r.time_sec ?? 0)
  const rankPart = r.achieved_rank_label ? `, разряд ${r.achieved_rank_label}` : ''
  const subtitle = isLongest ? 'Моя самая длинная дистанция' : `${r.distance_label}${rankPart}`
  share({ emoji: '⏱️', title, subtitle, utmCampaign: 'personal_record' })
}

onMounted(async () => {
  try {
    const res = await achievementsApi.list()
    genderRequired.value = res.gender_required
    personalRecords.value = res.personal_records
    badges.value = res.badges
  } finally {
    loading.value = false
  }
})
</script>

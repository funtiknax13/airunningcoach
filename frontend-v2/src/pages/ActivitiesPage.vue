<template>
  <AppLayout>
    <div class="activities-toolbar">
      <button class="btn btn-secondary btn-sm" @click="triggerFileInput" :disabled="importing">
        <i class="fas fa-file-import"></i> {{ importing ? $t('activities.importing') : $t('activities.importBtn') }}
      </button>
      <button class="btn btn-primary btn-sm" @click="modal?.open()">
        <i class="fas fa-plus"></i> {{ $t('activities.add') }}
      </button>
      <input ref="fileInput" type="file" accept=".gpx,.fit" style="display:none" @change="onFileSelected" />
    </div>

    <div v-if="importError" class="alert alert-error" style="margin-bottom:12px">
      <i class="fas fa-triangle-exclamation"></i> {{ importError }}
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <i class="fas fa-person-running"></i>
          {{ $t('activities.title') }}
        </div>
        <div class="act-tabs">
          <button class="act-tab" :class="{ active: activeTab === 'runs' }" @click="setTab('runs')">
            <i class="fas fa-person-running"></i> {{ $t('activities.tabRuns') }}
            <span class="act-tab-count">{{ runsCount }}</span>
          </button>
          <button class="act-tab" :class="{ active: activeTab === 'other' }" @click="setTab('other')">
            <i class="fas fa-dumbbell"></i> {{ $t('activities.tabOther') }}
            <span class="act-tab-count">{{ otherCount }}</span>
          </button>
        </div>
      </div>

      <SkeletonLoader v-if="store.loading" type="activity-list" :count="5" />
      <div v-else-if="!currentTabItems.length" class="empty-state">
        <i :class="activeTab === 'runs' ? 'fas fa-person-running' : 'fas fa-dumbbell'"></i>
        <p>{{ $t('activities.empty') }}</p>
      </div>
      <template v-else>
        <div v-for="act in pagedItems" :key="act.id" class="activity-row-wrap">
          <div class="activity-row" :class="{ 'activity-row--expanded': expandedId === act.id }">
            <div class="activity-row-icon">
              <i :class="activityIcon(act.activity_type)"></i>
            </div>
            <div class="activity-row-info" style="cursor:pointer" @click="toggleExpand(act.id)">
              <div class="activity-row-date">{{ formatDate(act.date) }}</div>
              <div class="activity-row-note">{{ act.notes || activityLabel(act.activity_type) }}</div>
            </div>
            <div class="activity-row-stats">
              <div class="activity-stat">
                <span class="activity-stat-val" style="color:var(--brand)">{{ act.distance_km }}</span>
                <span class="activity-stat-lbl">km</span>
              </div>
              <div v-if="act.activity_type === 'run'" class="activity-stat">
                <span class="activity-stat-val">{{ formatPace(act.pace_min_per_km) }}</span>
                <span class="activity-stat-lbl">{{ $t('stats.pace') }}</span>
              </div>
              <div class="activity-stat">
                <span class="activity-stat-val">{{ formatDuration(act.duration_min) }}</span>
                <span class="activity-stat-lbl">{{ $t('stats.time') }}</span>
              </div>
              <div v-if="act.avg_heart_rate" class="activity-stat">
                <span class="activity-stat-val" style="color:var(--red)">{{ act.avg_heart_rate }}</span>
                <span class="activity-stat-lbl">bpm</span>
              </div>
              <div v-if="act.elevation_gain" class="activity-stat">
                <span class="activity-stat-val" style="color:#10b981">{{ Math.round(act.elevation_gain) }}</span>
                <span class="activity-stat-lbl">м↑</span>
              </div>
            </div>
            <div class="activity-row-actions">
              <button class="edit-btn"
                :class="{ active: expandedId === act.id }"
                @click="toggleExpand(act.id)"
                :title="expandedId === act.id ? 'Свернуть' : 'Подробнее'">
                <i class="fas" :class="expandedId === act.id ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
              </button>
              <button class="edit-btn" @click="modal?.open(act.id)"><i class="fas fa-pen"></i></button>
              <button class="delete-btn" @click="confirmDelete(act.id)"><i class="fas fa-trash"></i></button>
            </div>
          </div>
          <Transition name="act-expand">
            <div v-if="expandedId === act.id" class="activity-detail-panel">
              <ActivityDetailComponent :activity-id="act.id" />
            </div>
          </Transition>
        </div>

        <div v-if="tabPages > 1" class="pager">
          <button class="pager-btn" :disabled="tabPage === 0" @click="tabPage--">
            <i class="fas fa-chevron-left"></i>
          </button>
          <span class="pager-info">{{ tabPage + 1 }} / {{ tabPages }}</span>
          <button class="pager-btn" :disabled="tabPage >= tabPages - 1" @click="tabPage++">
            <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </template>
    </div>

    <ActivityModal ref="modal" v-model="showModal" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import ActivityModal from '@/components/activities/ActivityModal.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import ActivityDetailComponent from '@/components/activities/ActivityDetail.vue'
import { useActivitiesStore } from '@/stores/activities'
import { useChatStore } from '@/stores/chat'
import { useDialog } from '@/composables/useDialog'
import { activitiesApi } from '@/api'
import { ApiError } from '@/api/client'
import { activityIcon, activityLabel as sharedActivityLabel } from '@/utils/activity'

const { t, locale } = useI18n()
const store     = useActivitiesStore()
const modal     = ref<InstanceType<typeof ActivityModal> | null>(null)
const showModal = ref(false)
const { confirm } = useDialog()
const fileInput   = ref<HTMLInputElement | null>(null)
const importing   = ref(false)
const importError = ref('')
const expandedId  = ref<number | null>(null)
const activeTab   = ref<'runs' | 'other'>('runs')
const tabPage     = ref(0)

const PAGE_SIZE = 7
const RUN_TYPES = ['run']

const runsCount  = computed(() => store.all.filter(a => RUN_TYPES.includes(a.activity_type ?? 'run')).length)
const otherCount = computed(() => store.all.filter(a => !RUN_TYPES.includes(a.activity_type ?? 'run')).length)

const currentTabItems = computed(() =>
  activeTab.value === 'runs'
    ? store.all.filter(a => RUN_TYPES.includes(a.activity_type ?? 'run'))
    : store.all.filter(a => !RUN_TYPES.includes(a.activity_type ?? 'run'))
)
const tabPages = computed(() => Math.max(1, Math.ceil(currentTabItems.value.length / PAGE_SIZE)))
const pagedItems = computed(() =>
  currentTabItems.value.slice(tabPage.value * PAGE_SIZE, (tabPage.value + 1) * PAGE_SIZE)
)

function setTab(tab: 'runs' | 'other') {
  activeTab.value = tab
  tabPage.value = 0
}

onMounted(() => store.load())

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

function triggerFileInput() {
  importError.value = ''
  fileInput.value?.click()
}

async function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value = true
  importError.value = ''
  try {
    const result = await activitiesApi.importFile(file)
    if (result.ai_analysis_pending) useChatStore().setUnread()
    await store.load()
  } catch (err: any) {
    if (err instanceof ApiError && err.status === 409 &&
        (err.detail as any)?.code === 'duplicate_activity') {
      importError.value = t('activities.duplicate')
    } else {
      importError.value = err.message || t('activities.errDateDist')
    }
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function activityLabel(type: string): string {
  return sharedActivityLabel(type, locale.value)
}

function formatPace(p: number) {
  const m = Math.floor(p); const s = Math.round((p - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function formatDuration(min: number) {
  const h = Math.floor(min / 60); const m = Math.round(min % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(
    locale.value === 'ru' ? 'ru-RU' : 'en-US',
    { day: '2-digit', month: 'short', year: 'numeric' }
  )
}
async function confirmDelete(id: number) {
  const ok = await confirm(
    t('activities.confirmDelete'),
    { danger: true, cancelLabel: t('btn.cancel'), confirmLabel: t('btn.delete') }
  )
  if (!ok) return
  await store.remove(id)
}
</script>

<template>
  <AppLayout>
    <template #header-actions>
      <button class="btn btn-secondary btn-sm" @click="triggerFileInput" :disabled="importing">
        <i class="fas fa-file-import"></i> {{ importing ? 'Импорт...' : 'Импорт GPX/FIT' }}
      </button>
      <button class="btn btn-primary btn-sm" @click="modal?.open()">
        <i class="fas fa-plus"></i> {{ $t('activities.add') }}
      </button>
      <input ref="fileInput" type="file" accept=".gpx,.fit" style="display:none" @change="onFileSelected" />
    </template>

    <div v-if="importError" class="alert alert-error" style="margin-bottom:12px">
      <i class="fas fa-triangle-exclamation"></i> {{ importError }}
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <i class="fas fa-person-running"></i>
          {{ $t('activities.title') }}
          <span style="color:var(--text-3);font-weight:400;text-transform:none;letter-spacing:0;font-size:0.8rem;margin-left:4px">
            ({{ store.all.length }})
          </span>
        </div>
      </div>

      <SkeletonLoader v-if="store.loading" type="activity-list" :count="5" />
      <div v-else-if="!store.all.length" class="empty-state">
        <i class="fas fa-person-running"></i>
        <p>{{ $t('activities.empty') }}</p>
      </div>
      <template v-else>
      <div v-for="act in store.current" :key="act.id" class="activity-row-wrap">
        <div class="activity-row" :class="{ 'activity-row--expanded': expandedId === act.id }">
          <div class="activity-row-icon"><i class="fas fa-person-running"></i></div>
          <div class="activity-row-info" style="cursor:pointer" @click="toggleExpand(act.id)">
            <div class="activity-row-date">{{ formatDate(act.date) }}</div>
            <div class="activity-row-note">{{ act.notes || $t('dash.run') }}</div>
          </div>
          <div class="activity-row-stats">
            <div class="activity-stat">
              <span class="activity-stat-val" style="color:var(--brand)">{{ act.distance_km }}</span>
              <span class="activity-stat-lbl">km</span>
            </div>
            <div class="activity-stat">
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
            <button class="edit-btn"   @click="modal?.open(act.id)"><i class="fas fa-pen"></i></button>
            <button class="delete-btn" @click="confirmDelete(act.id)"><i class="fas fa-trash"></i></button>
          </div>
        </div>
        <!-- Раскрытая детальная панель -->
        <Transition name="act-expand">
          <div v-if="expandedId === act.id" class="activity-detail-panel">
            <ActivityDetailComponent :activity-id="act.id" />
          </div>
        </Transition>
      </div>

      <!-- Pager -->
      <div v-if="store.pages > 1" class="pager">
        <button class="pager-btn" :disabled="store.page === 0" @click="store.setPage(store.page-1)">
          <i class="fas fa-chevron-left"></i>
        </button>
        <span class="pager-info">{{ store.page+1 }} / {{ store.pages }}</span>
        <button class="pager-btn" :disabled="store.page >= store.pages-1" @click="store.setPage(store.page+1)">
          <i class="fas fa-chevron-right"></i>
        </button>
      </div>
      </template>
    </div>

    <ActivityModal ref="modal" v-model="showModal" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import ActivityModal from '@/components/activities/ActivityModal.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import { useActivitiesStore } from '@/stores/activities'
import { useDialog } from '@/composables/useDialog'
import { activitiesApi } from '@/api'
import ActivityDetailComponent from '@/components/activities/ActivityDetail.vue'

const { t, locale } = useI18n()
const store     = useActivitiesStore()
const modal     = ref<InstanceType<typeof ActivityModal> | null>(null)
const showModal = ref(false)
const { confirm } = useDialog()
const fileInput    = ref<HTMLInputElement | null>(null)
const importing    = ref(false)
const importError  = ref('')
const expandedId   = ref<number | null>(null)

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(() => store.load())

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
    await activitiesApi.importFile(file)
    await store.load()
  } catch (err: any) {
    importError.value = err.message || 'Ошибка импорта файла'
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function formatPace(p: number) {
  const m = Math.floor(p); const s = Math.round((p-m)*60)
  return `${m}:${String(s).padStart(2,'0')}`
}
function formatDuration(min: number) {
  const h = Math.floor(min/60); const m = Math.round(min%60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(locale.value === 'ru' ? 'ru-RU' : 'en-US', { day:'2-digit', month:'short', year:'numeric' })
}
async function confirmDelete(id: number) {
  const ok = await confirm(t('activities.confirmDelete'), { danger: true, cancelLabel: t('btn.cancel'), confirmLabel: t('btn.delete') })
  if (!ok) return
  await store.remove(id)
}
</script>

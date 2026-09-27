<template>
  <BaseModal v-model="show">
    <h3 class="pdm-title">{{ t('plan.data.title') }}</h3>
    <p class="pdm-lead">{{ t('plan.data.lead') }}</p>

    <div class="pdm-tabs" role="tablist">
      <button v-for="k in tabs" :key="k" type="button" class="pdm-tab" :class="{ active: tab === k }" @click="tab = k">
        {{ t(`plan.data.tab${k[0].toUpperCase()}${k.slice(1)}`) }}
      </button>
    </div>

    <!-- Пробежка: файл или вручную -->
    <div v-if="tab === 'run'" class="pdm-body">
      <p class="pdm-hint">{{ t('plan.data.runHint') }}</p>
      <label class="pdm-file">
        <input type="file" accept=".gpx,.fit" @change="onFile">
        <i class="fas fa-file-arrow-up"></i>
        <span>{{ file ? file.name : t('plan.data.file') }}</span>
      </label>
      <p class="pdm-or">{{ t('plan.data.or') }}</p>
      <div class="pdm-grid">
        <div>
          <label class="modal-label">{{ t('plan.data.date') }}</label>
          <input type="date" class="modal-input" v-model="run.date" :max="todayStr">
        </div>
        <div>
          <label class="modal-label">{{ t('plan.data.distance') }}</label>
          <input type="number" step="0.01" min="0.5" class="modal-input" v-model.number="run.distance" :disabled="!!file">
        </div>
        <div>
          <label class="modal-label">{{ t('plan.data.time') }}</label>
          <input type="text" inputmode="numeric" class="modal-input" placeholder="32:15" v-model="run.time" :disabled="!!file">
        </div>
      </div>
      <label class="modal-label">{{ t('plan.data.effort') }}</label>
      <div class="pdm-chips">
        <button type="button" class="pdm-chip" :class="{ active: run.effort === 'easy' }" @click="run.effort = 'easy'">{{ t('plan.data.effortEasy') }}</button>
        <button type="button" class="pdm-chip" :class="{ active: run.effort === 'hard' }" @click="run.effort = 'hard'">{{ t('plan.data.effortHard') }}</button>
      </div>
    </div>

    <!-- Недавний результат -->
    <div v-else-if="tab === 'result'" class="pdm-body">
      <p class="pdm-hint">{{ t('plan.data.resultHint') }}</p>
      <label class="modal-label">{{ t('plan.data.distance') }}</label>
      <div class="pdm-chips">
        <button v-for="d in raceDistances" :key="d" type="button" class="pdm-chip"
          :class="{ active: result.distance === d }" @click="result.distance = d">{{ d }}</button>
      </div>
      <input type="number" step="0.01" min="0.8" class="modal-input" v-model.number="result.distance">
      <label class="modal-label">{{ t('plan.data.time') }}</label>
      <input type="text" inputmode="numeric" class="modal-input" placeholder="32:15" v-model="result.time">
    </div>

    <!-- Мой лёгкий темп -->
    <div v-else class="pdm-body">
      <p class="pdm-hint">{{ t('plan.data.paceHint') }}</p>
      <label class="modal-label">{{ t('plan.data.pace') }}</label>
      <input type="text" inputmode="numeric" class="modal-input" placeholder="7:30" v-model="pace">
    </div>

    <div v-if="error" class="auth-error">{{ error }}</div>
    <div class="modal-buttons">
      <button class="btn-primary" :disabled="saving" @click="save">
        <i v-if="saving" class="fas fa-spinner fa-spin"></i> {{ t('plan.data.save') }}
      </button>
      <button class="btn-secondary" :disabled="saving" @click="skip">{{ t('plan.data.skip') }}</button>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/common/BaseModal.vue'
import { activitiesApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useActivitiesStore } from '@/stores/activities'
import { parseDuration, parsePace } from '@/utils/time'

const show = defineModel<boolean>({ default: false })
const emit = defineEmits<{ (e: 'proceed'): void }>()
const { t } = useI18n()
const auth = useAuthStore()
const activities = useActivitiesStore()

const tabs = ['run', 'result', 'pace'] as const
const tab = ref<(typeof tabs)[number]>('run')
const saving = ref(false)
const error = ref('')
const file = ref<File | null>(null)

const todayStr = new Date().toISOString().slice(0, 10)
const run = ref({ date: todayStr, distance: null as number | null, time: '', effort: 'easy' as 'easy' | 'hard' })
const raceDistances = [5, 10, 21.1, 42.2]
const result = ref({ distance: 5 as number | null, time: '' })
const pace = ref('')

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null
  file.value = f
}

function close() { show.value = false }
function skip() { close(); emit('proceed') }

async function save() {
  error.value = ''
  saving.value = true
  try {
    if (tab.value === 'run') {
      if (file.value) {
        const created = await activitiesApi.importFile(file.value)
        await activitiesApi.update(created.id, { effort: run.value.effort })
      } else {
        const mins = parseDuration(run.value.time)
        if (!run.value.distance || run.value.distance <= 0 || mins == null) { error.value = t('plan.data.errRun'); return }
        await activitiesApi.create({
          date: new Date(`${run.value.date}T12:00:00`).toISOString(),
          distance_km: run.value.distance, duration_min: Math.round(mins * 100) / 100,
          activity_type: 'run', source: 'manual', effort: run.value.effort,
        })
      }
      activities.load()
    } else if (tab.value === 'result') {
      const mins = parseDuration(result.value.time)
      if (!result.value.distance || result.value.distance < 0.8 || mins == null) { error.value = t('plan.data.errTime'); return }
      await auth.updateProfile({ race_distance_km: result.value.distance, race_time_min: Math.round(mins * 100) / 100 })
    } else {
      const p = parsePace(pace.value)
      if (p == null) { error.value = t('plan.data.errPace'); return }
      await auth.updateProfile({ easy_pace_min_km: Math.round(p * 100) / 100 })
    }
    close()
    emit('proceed')
  } catch (e: any) {
    error.value = e?.message || 'Error'
  } finally {
    saving.value = false
  }
}

defineExpose({ open: () => { error.value = ''; file.value = null; show.value = true } })
</script>

<style scoped>
.pdm-title { margin: 0 0 6px; font-size: 1.1rem; font-weight: 800; }
.pdm-lead { margin: 0 0 12px; font-size: 0.85rem; line-height: 1.45; color: var(--text-2); }
.pdm-tabs { display: inline-flex; gap: 2px; padding: 3px; border-radius: 10px; background: var(--surface-3); margin-bottom: 4px; }
.pdm-tab {
  border: none; background: none; cursor: pointer; padding: 7px 14px; border-radius: 8px;
  font: inherit; font-size: 0.84rem; font-weight: 600; color: var(--text-2);
}
.pdm-tab.active { background: var(--surface); color: var(--text); box-shadow: var(--shadow-sm); }
.pdm-body { margin-top: 6px; }
.pdm-hint { margin: 6px 0; font-size: 0.8rem; color: var(--text-3); }
.pdm-or { margin: 8px 0 0; text-align: center; font-size: 0.75rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; }
.pdm-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0 10px; }
.pdm-file {
  display: flex; align-items: center; gap: 10px; padding: 10px 13px; border: 1px dashed var(--border-2);
  border-radius: var(--r); cursor: pointer; color: var(--text-2); font-size: 0.85rem;
}
.pdm-file:hover { border-color: var(--brand); color: var(--text); }
.pdm-file input { display: none; }
.pdm-file i { color: var(--brand); }
.pdm-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 4px; }
.pdm-chip {
  border: 1px solid var(--border); background: var(--surface); color: var(--text-2);
  border-radius: 99px; padding: 7px 13px; font: inherit; font-size: 0.82rem; font-weight: 600; cursor: pointer;
}
.pdm-chip.active { background: var(--brand); border-color: var(--brand); color: #fff; }
</style>
